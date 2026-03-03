"""Email Intelligence — connects to Microsoft 365 to track supplier orders.

Modules:
    connector  — Microsoft Graph API client (OAuth2, email search)
    parser     — Extracts design names, quantities, and dates from order emails
    tracker    — Manages pending supplier orders and feeds into Print Forecaster
"""

from email_intel.connector import OutlookConnector
from email_intel.parser import parse_order_email, parse_multiple_emails
from email_intel.tracker import PendingOrderTracker
