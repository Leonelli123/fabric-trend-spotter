#!/usr/bin/env python3
"""Quick test: verify e-conomic API connection with your tokens.

Usage:
    python test_economic_connection.py
"""

import sys
import os

# Load .env first
from dotenv import load_dotenv
load_dotenv()

from economic_intel.connector import EconomicConnector

app_secret = os.environ.get("ECONOMIC_APP_SECRET", "")
grant_token = os.environ.get("ECONOMIC_GRANT_TOKEN", "")

if not app_secret or app_secret == "PASTE_YOUR_APP_SECRET_HERE":
    print("ERROR: ECONOMIC_APP_SECRET is not set in .env")
    print("  Open .env and replace PASTE_YOUR_APP_SECRET_HERE with your real token")
    sys.exit(1)

if not grant_token or grant_token == "PASTE_YOUR_GRANT_TOKEN_HERE":
    print("ERROR: ECONOMIC_GRANT_TOKEN is not set in .env")
    print("  Open .env and replace PASTE_YOUR_GRANT_TOKEN_HERE with your real token")
    sys.exit(1)

print("Connecting to e-conomic API...")
eco = EconomicConnector(app_secret=app_secret, grant_token=grant_token)
result = eco.test_connection()

if result["connected"]:
    print(f"  Connected to: {result['company_name']}")
    print(f"  Agreement #:  {result['agreement_number']}")
    print()

    # Quick data test
    print("Fetching recent invoices (last 90 days)...")
    invoices = eco.get_booked_invoices(days_back=90)
    print(f"  Found {len(invoices)} booked invoices")

    if invoices:
        latest = invoices[0]
        print(f"  Latest: #{latest['invoice_number']} — {latest['customer_name']} — "
              f"{latest['gross_amount']} {latest['currency']}")

    print()
    print("Fetching customers...")
    customers = eco.get_customers()
    print(f"  Found {len(customers)} customers")

    print()
    print("ALL GOOD — e-conomic is connected and pulling real data!")
else:
    print(f"  Connection FAILED: {result['error']}")
    print()
    print("Common fixes:")
    print("  1. Double-check that ECONOMIC_APP_SECRET in .env is the App Secret Token (not the app name)")
    print("  2. Double-check that ECONOMIC_GRANT_TOKEN is the Agreement Grant Token")
    print("  3. Make sure the app has 'Read-only' role in e-conomic")
    print("  4. Make sure you completed the installation step (clicked 'Add app' on the authorization URL)")
    sys.exit(1)
