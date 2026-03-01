"""e-conomic Financial Intelligence — the source of truth for invoices and payments.

Modules:
    connector   — e-conomic REST API client (invoices, customers, products)
    analyzer    — Revenue breakdown, accounts receivable, customer profitability
    reconciler  — Cross-references WooCommerce orders with e-conomic invoices
"""

from economic_intel.connector import EconomicConnector
from economic_intel.analyzer import FinancialAnalyzer
from economic_intel.reconciler import DataReconciler
