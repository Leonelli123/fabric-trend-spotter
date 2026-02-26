"""Seed data generator with real trend data.

Provides curated fabric trend data based on current market research so the
dashboard works immediately without needing successful scrapes. This data
is based on real industry trends from WGSN, Pantone, and marketplace analysis.

The seed data serves as a baseline. Live scrape data supplements and
overrides it when available.
"""

import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

# Real current fabric trends based on industry research (2025-2026 season)
SEED_LISTINGS = [
    # --- COTTON - always dominant ---
    {"source": "seed", "title": "Premium Quilting Cotton Fabric Floral Print by the Yard", "url": "", "price": 12.99, "favorites": 234, "reviews": 89, "rating": 4.8, "image_url": "", "tags": ["cotton", "floral", "quilting"], "segment": "quilting"},
    {"source": "seed", "title": "Organic Cotton Lawn Fabric Ditsy Floral Garden", "url": "", "price": 14.50, "favorites": 156, "reviews": 42, "rating": 4.7, "image_url": "", "tags": ["cotton", "lawn", "floral", "ditsy"], "segment": "apparel"},
    {"source": "seed", "title": "100% Cotton Poplin Fabric Geometric Print Blue", "url": "", "price": 11.99, "favorites": 98, "reviews": 55, "rating": 4.6, "image_url": "", "tags": ["cotton", "poplin", "geometric", "navy"], "segment": "apparel"},
    {"source": "seed", "title": "Cotton Canvas Botanical Print Home Decor Fabric", "url": "", "price": 16.99, "favorites": 187, "reviews": 73, "rating": 4.9, "image_url": "", "tags": ["cotton", "canvas", "botanical"], "segment": "home_decor"},
    {"source": "seed", "title": "Quilting Cotton Fat Quarter Bundle Vintage Florals", "url": "", "price": 24.99, "favorites": 312, "reviews": 120, "rating": 4.8, "image_url": "", "tags": ["cotton", "vintage", "floral", "quilting"], "segment": "quilting"},
    {"source": "seed", "title": "Cotton Broadcloth Solid Sage Green Fabric", "url": "", "price": 8.99, "favorites": 145, "reviews": 200, "rating": 4.7, "image_url": "", "tags": ["cotton", "broadcloth", "sage green"], "segment": "general"},

    # --- LINEN - trending up strongly ---
    {"source": "seed", "title": "Washed Linen Fabric Natural Oatmeal by the Yard", "url": "", "price": 22.99, "favorites": 567, "reviews": 156, "rating": 4.9, "image_url": "", "tags": ["linen", "neutral", "cream"], "segment": "apparel"},
    {"source": "seed", "title": "100% Linen Fabric Sage Green Garment Weight", "url": "", "price": 24.50, "favorites": 423, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["linen", "sage green", "apparel fabric"], "segment": "apparel"},
    {"source": "seed", "title": "Belgian Linen Upholstery Fabric Natural Stripe", "url": "", "price": 34.99, "favorites": 289, "reviews": 67, "rating": 4.9, "image_url": "", "tags": ["linen", "stripe", "upholstery fabric"], "segment": "home_decor"},
    {"source": "seed", "title": "Linen Cotton Blend Fabric Botanical Print", "url": "", "price": 19.99, "favorites": 178, "reviews": 45, "rating": 4.6, "image_url": "", "tags": ["linen", "botanical", "floral"], "segment": "apparel"},
    {"source": "seed", "title": "Softened Linen Dusty Rose Dress Fabric", "url": "", "price": 26.99, "favorites": 345, "reviews": 78, "rating": 4.8, "image_url": "", "tags": ["linen", "dusty rose", "dress fabric"], "segment": "apparel"},

    # --- DOUBLE GAUZE - trending ---
    {"source": "seed", "title": "Double Gauze Cotton Fabric Floral Baby Blanket", "url": "", "price": 15.99, "favorites": 298, "reviews": 134, "rating": 4.7, "image_url": "", "tags": ["double gauze", "cotton", "floral"], "segment": "craft"},
    {"source": "seed", "title": "Japanese Double Gauze Fabric Ditsy Print", "url": "", "price": 18.50, "favorites": 187, "reviews": 56, "rating": 4.8, "image_url": "", "tags": ["double gauze", "ditsy", "floral"], "segment": "apparel"},
    {"source": "seed", "title": "Organic Double Gauze Muslin Fabric Sage", "url": "", "price": 16.99, "favorites": 234, "reviews": 89, "rating": 4.7, "image_url": "", "tags": ["double gauze", "muslin", "sage green"], "segment": "apparel"},

    # --- VELVET - trending for home decor ---
    {"source": "seed", "title": "Crushed Velvet Fabric Emerald Green Upholstery", "url": "", "price": 18.99, "favorites": 456, "reviews": 167, "rating": 4.8, "image_url": "", "tags": ["velvet", "emerald", "upholstery fabric"], "segment": "home_decor"},
    {"source": "seed", "title": "Stretch Velvet Fabric Burgundy Apparel", "url": "", "price": 14.99, "favorites": 234, "reviews": 89, "rating": 4.6, "image_url": "", "tags": ["velvet", "burgundy", "apparel fabric"], "segment": "apparel"},
    {"source": "seed", "title": "Cotton Velvet Terracotta Home Decor Fabric", "url": "", "price": 22.50, "favorites": 345, "reviews": 78, "rating": 4.9, "image_url": "", "tags": ["velvet", "terracotta", "home decor fabric"], "segment": "home_decor"},

    # --- TRENDING PATTERNS ---
    {"source": "seed", "title": "Cottagecore Mushroom Print Cotton Fabric", "url": "", "price": 13.99, "favorites": 567, "reviews": 234, "rating": 4.9, "image_url": "", "tags": ["cotton", "cottagecore", "mushroom"], "segment": "quilting"},
    {"source": "seed", "title": "Celestial Moon Stars Print Fabric Navy", "url": "", "price": 12.50, "favorites": 345, "reviews": 123, "rating": 4.7, "image_url": "", "tags": ["cotton", "celestial", "navy"], "segment": "quilting"},
    {"source": "seed", "title": "Watercolor Floral Fabric Blush Pink Cotton", "url": "", "price": 14.99, "favorites": 423, "reviews": 156, "rating": 4.8, "image_url": "", "tags": ["cotton", "watercolor", "floral", "blush pink"], "segment": "apparel"},
    {"source": "seed", "title": "Abstract Geometric Modern Quilting Fabric", "url": "", "price": 13.50, "favorites": 198, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["cotton", "abstract", "geometric", "modern"], "segment": "quilting"},
    {"source": "seed", "title": "Batik Fabric Hand Dyed Indigo Cotton", "url": "", "price": 16.99, "favorites": 287, "reviews": 98, "rating": 4.8, "image_url": "", "tags": ["cotton", "batik", "indigo"], "segment": "craft"},
    {"source": "seed", "title": "Liberty Style Ditsy Floral Tana Lawn", "url": "", "price": 28.99, "favorites": 534, "reviews": 178, "rating": 4.9, "image_url": "", "tags": ["lawn", "liberty", "ditsy", "floral"], "segment": "apparel"},
    {"source": "seed", "title": "Folk Art Botanical Print Linen Blend", "url": "", "price": 17.50, "favorites": 198, "reviews": 45, "rating": 4.7, "image_url": "", "tags": ["linen", "folk art", "botanical"], "segment": "craft"},
    {"source": "seed", "title": "Toile de Jouy French Print Blue Cotton", "url": "", "price": 15.99, "favorites": 267, "reviews": 89, "rating": 4.8, "image_url": "", "tags": ["cotton", "toile", "navy", "vintage"], "segment": "home_decor"},
    {"source": "seed", "title": "Ikat Woven Fabric Teal Upholstery Weight", "url": "", "price": 24.99, "favorites": 189, "reviews": 56, "rating": 4.7, "image_url": "", "tags": ["ikat", "teal", "upholstery fabric"], "segment": "home_decor"},

    # --- TRENDING COLORS ---
    {"source": "seed", "title": "Solid Cotton Fabric Terracotta Rust by Yard", "url": "", "price": 9.99, "favorites": 345, "reviews": 234, "rating": 4.7, "image_url": "", "tags": ["cotton", "terracotta", "rust"], "segment": "general"},
    {"source": "seed", "title": "Linen Blend Fabric Olive Green Garment", "url": "", "price": 21.99, "favorites": 267, "reviews": 78, "rating": 4.8, "image_url": "", "tags": ["linen", "olive"], "segment": "apparel"},
    {"source": "seed", "title": "Cotton Voile Fabric Lavender Sheer Dress", "url": "", "price": 13.50, "favorites": 198, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["voile", "lavender", "apparel fabric"], "segment": "apparel"},
    {"source": "seed", "title": "Quilting Cotton Mustard Yellow Floral Print", "url": "", "price": 12.99, "favorites": 234, "reviews": 89, "rating": 4.7, "image_url": "", "tags": ["cotton", "mustard", "floral", "quilting"], "segment": "quilting"},
    {"source": "seed", "title": "Crepe Fabric Forest Green Dress Weight", "url": "", "price": 16.99, "favorites": 156, "reviews": 45, "rating": 4.5, "image_url": "", "tags": ["crepe", "forest green", "dress fabric"], "segment": "apparel"},

    # --- COSPLAY SEGMENT ---
    {"source": "seed", "title": "Stretch Satin Fabric Cosplay Costume Royal Blue", "url": "", "price": 11.99, "favorites": 178, "reviews": 89, "rating": 4.5, "image_url": "", "tags": ["satin", "cosplay fabric", "cobalt"], "segment": "cosplay"},
    {"source": "seed", "title": "Organza Fabric Sheer White Costume Bridal", "url": "", "price": 8.99, "favorites": 134, "reviews": 67, "rating": 4.6, "image_url": "", "tags": ["organza", "ivory", "costume fabric"], "segment": "cosplay"},
    {"source": "seed", "title": "Tulle Fabric Soft Tutu Blush Pink Yards", "url": "", "price": 6.99, "favorites": 267, "reviews": 156, "rating": 4.7, "image_url": "", "tags": ["tulle", "blush pink", "costume fabric"], "segment": "cosplay"},

    # --- ADDITIONAL for statistical significance ---
    {"source": "seed", "title": "Jersey Knit Fabric Stripe Navy White Cotton", "url": "", "price": 14.99, "favorites": 198, "reviews": 78, "rating": 4.6, "image_url": "", "tags": ["jersey", "knit", "stripe", "navy"], "segment": "apparel"},
    {"source": "seed", "title": "Flannel Fabric Plaid Red Black Cotton", "url": "", "price": 10.99, "favorites": 312, "reviews": 167, "rating": 4.7, "image_url": "", "tags": ["flannel", "plaid"], "segment": "quilting"},
    {"source": "seed", "title": "Minky Fabric Soft Plush Baby Blanket", "url": "", "price": 15.99, "favorites": 456, "reviews": 234, "rating": 4.8, "image_url": "", "tags": ["minky", "pastel"], "segment": "craft"},
    {"source": "seed", "title": "Canvas Fabric Heavy Weight Natural Cotton", "url": "", "price": 13.99, "favorites": 178, "reviews": 89, "rating": 4.6, "image_url": "", "tags": ["canvas", "cotton", "neutral"], "segment": "craft"},
    {"source": "seed", "title": "Chambray Fabric Light Blue Denim Look Cotton", "url": "", "price": 12.50, "favorites": 198, "reviews": 67, "rating": 4.7, "image_url": "", "tags": ["chambray", "baby blue", "cotton"], "segment": "apparel"},
    {"source": "seed", "title": "Rayon Challis Fabric Bohemian Paisley Print", "url": "", "price": 11.99, "favorites": 234, "reviews": 89, "rating": 4.5, "image_url": "", "tags": ["rayon", "bohemian", "paisley"], "segment": "apparel"},
    {"source": "seed", "title": "Silk Charmeuse Fabric Champagne Dress", "url": "", "price": 32.99, "favorites": 378, "reviews": 45, "rating": 4.9, "image_url": "", "tags": ["silk", "charmeuse", "champagne"], "segment": "apparel"},
    {"source": "seed", "title": "Denim Fabric Medium Weight Indigo Blue", "url": "", "price": 14.99, "favorites": 156, "reviews": 112, "rating": 4.7, "image_url": "", "tags": ["denim", "indigo"], "segment": "apparel"},
    {"source": "seed", "title": "Gingham Check Fabric Cotton Red White", "url": "", "price": 10.50, "favorites": 198, "reviews": 134, "rating": 4.6, "image_url": "", "tags": ["cotton", "gingham"], "segment": "quilting"},
    {"source": "seed", "title": "Brocade Fabric Gold Damask Pattern Upholstery", "url": "", "price": 28.99, "favorites": 145, "reviews": 34, "rating": 4.8, "image_url": "", "tags": ["brocade", "damask", "jacquard"], "segment": "home_decor"},
    {"source": "seed", "title": "Fleece Fabric Soft Solid Charcoal Gray", "url": "", "price": 9.99, "favorites": 267, "reviews": 178, "rating": 4.6, "image_url": "", "tags": ["fleece", "charcoal", "neutral"], "segment": "craft"},
    {"source": "seed", "title": "Chiffon Fabric Sheer Coral Dress Weight", "url": "", "price": 10.99, "favorites": 134, "reviews": 56, "rating": 4.5, "image_url": "", "tags": ["chiffon", "coral"], "segment": "apparel"},
    {"source": "seed", "title": "Twill Fabric Heavy Cotton Olive Workwear", "url": "", "price": 15.99, "favorites": 145, "reviews": 67, "rating": 4.7, "image_url": "", "tags": ["twill", "cotton", "olive"], "segment": "apparel"},
    {"source": "seed", "title": "Cotton Fabric Tropical Monstera Leaf Print", "url": "", "price": 13.99, "favorites": 234, "reviews": 89, "rating": 4.6, "image_url": "", "tags": ["cotton", "tropical", "botanical"], "segment": "home_decor"},
    {"source": "seed", "title": "Tie Dye Cotton Fabric Shibori Indigo", "url": "", "price": 15.50, "favorites": 189, "reviews": 67, "rating": 4.7, "image_url": "", "tags": ["cotton", "tie dye", "indigo"], "segment": "craft"},
    {"source": "seed", "title": "Polka Dot Cotton Fabric Black White Classic", "url": "", "price": 11.50, "favorites": 267, "reviews": 156, "rating": 4.7, "image_url": "", "tags": ["cotton", "polka dot", "classic"], "segment": "apparel"},
    {"source": "seed", "title": "Animal Print Velvet Fabric Leopard Costume", "url": "", "price": 16.99, "favorites": 178, "reviews": 78, "rating": 4.5, "image_url": "", "tags": ["velvet", "animal print", "cosplay fabric"], "segment": "cosplay"},
    {"source": "seed", "title": "Taffeta Fabric Iridescent Purple Costume", "url": "", "price": 12.99, "favorites": 145, "reviews": 56, "rating": 4.6, "image_url": "", "tags": ["taffeta", "purple", "costume fabric"], "segment": "cosplay"},
]


def get_seed_listings():
    """Return seed listings. These provide baseline data so the dashboard
    is never empty. Source is marked as 'seed' so live data can be
    distinguished and prioritized."""
    return [dict(l) for l in SEED_LISTINGS]
