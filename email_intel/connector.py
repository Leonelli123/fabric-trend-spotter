"""Microsoft Graph API connector for Outlook email access.

Uses OAuth2 authorization code flow to access the user's mailbox.
Searches sent items for supplier order emails and returns email content
for parsing.

Setup:
  1. Register an app in Azure AD (portal.azure.com > App registrations)
  2. Add redirect URI: https://your-app.com/auth/callback
  3. Under API permissions, add Microsoft Graph > Mail.Read (delegated)
  4. Create a client secret
  5. Set environment variables: MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID
"""

import logging
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
AUTH_BASE = "https://login.microsoftonline.com"


class OutlookConnector:
    """Microsoft Graph API client for reading emails."""

    SCOPES = "Mail.Read offline_access"

    def __init__(self, client_id: str, client_secret: str, tenant_id: str,
                 redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.redirect_uri = redirect_uri
        self._access_token = None
        self._refresh_token = None
        self._token_expires = 0
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # OAuth2 Authorization Code Flow
    # ------------------------------------------------------------------

    def get_auth_url(self, state: str = "") -> str:
        """Generate the Microsoft login URL to redirect the user to."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": self.SCOPES,
            "state": state,
        }
        return (
            f"{AUTH_BASE}/{self.tenant_id}/oauth2/v2.0/authorize?"
            + urlencode(params)
        )

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for access + refresh tokens."""
        resp = requests.post(
            f"{AUTH_BASE}/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "scope": self.SCOPES,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60
        logger.info("Microsoft Graph: obtained access token")
        return data

    def refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            logger.warning("No refresh token available")
            return False
        try:
            resp = requests.post(
                f"{AUTH_BASE}/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                    "scope": self.SCOPES,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._refresh_token = data.get("refresh_token", self._refresh_token)
            self._token_expires = time.time() + data.get("expires_in", 3600) - 60
            logger.info("Microsoft Graph: refreshed access token")
            return True
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            return False

    def set_tokens(self, access_token: str, refresh_token: str = None,
                   expires_at: float = 0):
        """Restore tokens from stored state (e.g., after app restart)."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires = expires_at

    def get_tokens(self) -> dict:
        """Return current token state for storage."""
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._token_expires,
        }

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def _ensure_token(self):
        """Refresh token if expired."""
        if time.time() >= self._token_expires and self._refresh_token:
            self.refresh_access_token()

    def _headers(self) -> dict:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Email Search
    # ------------------------------------------------------------------

    def search_sent_emails(self, supplier_email: str,
                           days_back: int = 180,
                           max_results: int = 50) -> list[dict]:
        """Search Sent Items for emails to the supplier.

        Args:
            supplier_email: The supplier's email address to search for.
            days_back: How far back to search (default 180 days).
            max_results: Maximum emails to return.

        Returns:
            List of email dicts with: id, subject, date, body, to, has_attachments.
        """
        if not self._access_token:
            logger.warning("Not authenticated — cannot search emails")
            return []

        after_date = (datetime.utcnow() - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT00:00:00Z"
        )

        # Search in SentItems folder for emails TO the supplier
        # Using $filter for reliability (vs $search which is fuzzy)
        params = {
            "$filter": (
                f"toRecipients/any(r: r/emailAddress/address eq "
                f"'{supplier_email}') and "
                f"sentDateTime ge {after_date}"
            ),
            "$orderby": "sentDateTime desc",
            "$top": max_results,
            "$select": "id,subject,sentDateTime,bodyPreview,body,toRecipients,hasAttachments",
        }

        try:
            resp = self._session.get(
                f"{GRAPH_BASE}/me/mailFolders/SentItems/messages",
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("value", [])

            results = []
            for msg in messages:
                results.append({
                    "id": msg["id"],
                    "subject": msg.get("subject", ""),
                    "date": msg.get("sentDateTime", ""),
                    "body_preview": msg.get("bodyPreview", ""),
                    "body_text": self._extract_text(msg.get("body", {})),
                    "to": [
                        r["emailAddress"]["address"]
                        for r in msg.get("toRecipients", [])
                    ],
                    "has_attachments": msg.get("hasAttachments", False),
                })

            logger.info(
                "Found %d sent emails to %s (last %d days)",
                len(results), supplier_email, days_back,
            )
            return results

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                logger.warning("Token expired, attempting refresh...")
                if self.refresh_access_token():
                    return self.search_sent_emails(
                        supplier_email, days_back, max_results
                    )
            logger.error("Email search failed: %s", e)
            return []
        except Exception as e:
            logger.error("Email search failed: %s", e)
            return []

    def get_email_by_id(self, message_id: str) -> dict | None:
        """Fetch a single email by its ID (full body)."""
        if not self._access_token:
            return None
        try:
            resp = self._session.get(
                f"{GRAPH_BASE}/me/messages/{message_id}",
                headers=self._headers(),
                params={"$select": "id,subject,sentDateTime,body,toRecipients"},
                timeout=30,
            )
            resp.raise_for_status()
            msg = resp.json()
            return {
                "id": msg["id"],
                "subject": msg.get("subject", ""),
                "date": msg.get("sentDateTime", ""),
                "body_text": self._extract_text(msg.get("body", {})),
            }
        except Exception as e:
            logger.error("Failed to fetch email %s: %s", message_id, e)
            return None

    def get_user_profile(self) -> dict | None:
        """Get the authenticated user's basic profile."""
        if not self._access_token:
            return None
        try:
            resp = self._session.get(
                f"{GRAPH_BASE}/me",
                headers=self._headers(),
                params={"$select": "displayName,mail,userPrincipalName"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Profile fetch failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(body: dict) -> str:
        """Extract plain text from email body (handles HTML and text)."""
        content = body.get("content", "")
        content_type = body.get("contentType", "text")

        if content_type.lower() == "html":
            # Basic HTML to text conversion
            import re
            # Remove style/script blocks
            text = re.sub(r"<style[^>]*>.*?</style>", "", content,
                          flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text,
                          flags=re.DOTALL | re.IGNORECASE)
            # Replace <br>, <p>, <div> with newlines
            text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
            text = re.sub(r"</(p|div|tr|li)>", "\n", text, flags=re.IGNORECASE)
            # Remove remaining HTML tags
            text = re.sub(r"<[^>]+>", "", text)
            # Clean up whitespace
            text = re.sub(r"&nbsp;", " ", text)
            text = re.sub(r"&amp;", "&", text)
            text = re.sub(r"&lt;", "<", text)
            text = re.sub(r"&gt;", ">", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

        return content.strip()
