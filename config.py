"""Configuration for the Fabric Trend Spotter."""

import os

# Etsy API (fill in when your key is approved)
ETSY_API_KEY = os.environ.get("ETSY_API_KEY", "")

# Scraping settings
REQUEST_DELAY = 2  # seconds between requests to be polite
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15

# Data refresh interval (hours)
REFRESH_INTERVAL_HOURS = 6

# Database - try local data/ dir, fall back to /tmp for cloud deployments
_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
try:
    os.makedirs(_data_dir, exist_ok=True)
    # Verify we can actually write there
    _test_path = os.path.join(_data_dir, ".write_test")
    with open(_test_path, "w") as _f:
        _f.write("ok")
    os.remove(_test_path)
except OSError:
    _data_dir = "/tmp/fabric-trend-spotter"
    os.makedirs(_data_dir, exist_ok=True)
DB_PATH = os.path.join(_data_dir, "trends.db")

# Flask
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fabric-spotter-key")
DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

# Fabric categories to track
FABRIC_TYPES = [
    "cotton", "linen", "silk", "wool", "polyester", "rayon", "chiffon",
    "denim", "velvet", "satin", "organza", "tulle", "muslin", "flannel",
    "fleece", "jersey", "knit", "canvas", "twill", "chambray",
    "double gauze", "lawn", "voile", "crepe", "taffeta", "brocade",
    "jacquard", "charmeuse", "poplin", "broadcloth", "minky",
]

PATTERN_TYPES = [
    "floral", "geometric", "abstract", "stripe", "plaid", "polka dot",
    "paisley", "animal print", "tropical", "botanical", "vintage",
    "retro", "modern", "minimalist", "bohemian", "toile",
    "damask", "ikat", "chevron", "gingham", "houndstooth",
    "tie dye", "batik", "watercolor", "ditsy", "liberty",
    "cottagecore", "mushroom", "celestial", "folk art",
]

COLOR_TERMS = [
    "sage green", "dusty rose", "navy", "terracotta", "mustard",
    "blush pink", "emerald", "burgundy", "cobalt", "mauve",
    "ivory", "rust", "olive", "lavender", "coral", "teal",
    "ochre", "indigo", "seafoam", "champagne", "charcoal",
    "burnt orange", "forest green", "baby blue", "cream",
    "earth tone", "jewel tone", "pastel", "neutral", "muted",
]
