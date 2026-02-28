"""WooCommerce Inventory Intelligence — the tool that tells you what to buy,
what to discount, and where your cash is stuck.

Modules:
    connector   — WooCommerce REST API client (products, orders, categories)
    analyzer    — Sales velocity, dead stock, winner detection, seasonal patterns
    recommender — Buy/hold/discount/cut recommendations with reasoning
    projections — Revenue forecasts, cash flow, inventory turnover
"""

from woo_intel.connector import WooConnector
from woo_intel.analyzer import InventoryAnalyzer
from woo_intel.recommender import ActionRecommender
from woo_intel.projections import RevenueProjector
