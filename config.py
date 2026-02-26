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
    "patina blue", "warm beige", "clay", "butter yellow",
]

# Market segments - each has tailored search queries and relevance weights
SEGMENTS = {
    "quilting": {
        "label": "Quilting",
        "icon": "grid",
        "keywords": [
            "quilting cotton", "fat quarter", "jelly roll", "charm pack",
            "quilt fabric", "patchwork", "quilting bundle", "precut fabric",
        ],
        "priority_patterns": [
            "floral", "geometric", "ditsy", "batik", "modern", "vintage",
        ],
        "priority_fabrics": ["cotton", "flannel", "minky", "broadcloth"],
    },
    "apparel": {
        "label": "Apparel Sewing",
        "icon": "scissors",
        "keywords": [
            "apparel fabric", "dress fabric", "garment fabric",
            "dressmaking", "fashion fabric", "sewing pattern fabric",
        ],
        "priority_patterns": [
            "floral", "stripe", "plaid", "abstract", "polka dot", "liberty",
        ],
        "priority_fabrics": [
            "linen", "cotton", "silk", "rayon", "jersey", "lawn", "voile",
            "crepe", "double gauze", "chambray", "chiffon",
        ],
    },
    "home_decor": {
        "label": "Home Decor",
        "icon": "home",
        "keywords": [
            "upholstery fabric", "curtain fabric", "home decor fabric",
            "throw pillow fabric", "slipcover", "drapery fabric",
        ],
        "priority_patterns": [
            "damask", "ikat", "toile", "geometric", "botanical", "stripe",
        ],
        "priority_fabrics": [
            "linen", "velvet", "canvas", "twill", "jacquard", "brocade",
        ],
    },
    "cosplay": {
        "label": "Cosplay & Costume",
        "icon": "sparkles",
        "keywords": [
            "cosplay fabric", "costume fabric", "spandex fabric",
            "metallic fabric", "faux leather", "holographic fabric",
        ],
        "priority_patterns": [
            "animal print", "abstract", "celestial", "geometric",
        ],
        "priority_fabrics": [
            "satin", "organza", "tulle", "velvet", "chiffon", "taffeta",
        ],
    },
    "craft": {
        "label": "Craft & Mixed Media",
        "icon": "palette",
        "keywords": [
            "craft fabric", "felt fabric", "embroidery fabric",
            "cross stitch", "fabric bundle", "scrap fabric",
        ],
        "priority_patterns": [
            "vintage", "retro", "cottagecore", "folk art", "bohemian",
        ],
        "priority_fabrics": ["cotton", "felt", "muslin", "canvas", "linen"],
    },
}

# Trend lifecycle thresholds
LIFECYCLE_THRESHOLDS = {
    "emerging": {"min_velocity": 0.5, "max_score": 25},
    "rising": {"min_velocity": 0.2, "min_score": 15, "max_score": 60},
    "peak": {"min_score": 55, "max_velocity": 0.3},
    "declining": {"max_velocity": -0.1},
    "stable": {"min_score": 20, "max_velocity": 0.2, "min_velocity": -0.1},
}

# --------------------------------------------------------------------------
# European Markets
# --------------------------------------------------------------------------
EUROPEAN_COUNTRIES = {
    "NL": {
        "name": "Netherlands",
        "flag": "\U0001F1F3\U0001F1F1",
        "currency": "EUR",
        "geo": "NL",
        "region": "western",
        "local_marketplaces": [
            "Stof&Stil NL", "Stoffenwinkel", "Textielstad", "Etsy NL",
            "De Stoffenkamer", "Mooie Stof", "Driessen Stoffen",
            "Bel'Etoile Fabrics", "De Naaihoek", "Stoff4you",
        ],
        "local_terms": [
            "stof per meter", "katoen stof", "linnen stof", "quiltstof",
            "naaistoffen", "bekledingsstof", "gordijnstof",
        ],
        "google_keywords": [
            "stof per meter", "quiltstof", "linnen stof", "naaistoffen",
            "katoen stof", "bekledingsstof", "tricot stof",
        ],
    },
    "DE": {
        "name": "Germany",
        "flag": "\U0001F1E9\U0001F1EA",
        "currency": "EUR",
        "geo": "DE",
        "region": "western",
        "local_marketplaces": [
            "Stoffe.de", "Stoffkontor", "Stoff&Stil DE", "Amazon.de",
            "Stoffwelten", "Nähwelt Flach", "myfabrics.co.uk (DE)",
            "Snaply", "Alles für Selbermacher", "Zierstoff",
            "Swafing", "Buttinette", "HEMMERS Itex",
        ],
        "local_terms": [
            "stoff meterware", "baumwollstoff", "leinenstoff", "patchworkstoff",
            "jersey stoff", "polsterstoff", "gardinenstoff", "dekostoff",
        ],
        "google_keywords": [
            "stoff meterware", "baumwollstoff", "patchworkstoff", "jersey stoff",
            "leinenstoff", "polsterstoff", "dekostoff",
        ],
    },
    "SE": {
        "name": "Sweden",
        "flag": "\U0001F1F8\U0001F1EA",
        "currency": "SEK",
        "geo": "SE",
        "region": "nordic",
        "local_marketplaces": ["Stoff&Stil SE", "Tyg.se", "Textilgallerian"],
        "local_terms": [
            "tyg metervara", "bomullstyg", "linnetyg", "quilttyg",
            "jerseytyg", "möbeltyg",
        ],
        "google_keywords": [
            "tyg metervara", "bomullstyg", "linnetyg", "quilttyg",
            "jerseytyg", "möbeltyg", "sy tyg",
        ],
    },
    "FI": {
        "name": "Finland",
        "flag": "\U0001F1EB\U0001F1EE",
        "currency": "EUR",
        "geo": "FI",
        "region": "nordic",
        "local_marketplaces": ["Eurokangas", "Kankaita", "Stoff&Stil FI"],
        "local_terms": [
            "kangas metrittäin", "puuvillakangas", "pellavakangas",
            "trikookangas", "tilkkutyökangas",
        ],
        "google_keywords": [
            "kangas metritavarana", "puuvillakangas", "pellavakangas",
            "trikookangas", "ompelu kangas",
        ],
    },
    "DK": {
        "name": "Denmark",
        "flag": "\U0001F1E9\U0001F1F0",
        "currency": "DKK",
        "geo": "DK",
        "region": "nordic",
        "local_marketplaces": ["Stof&Stil DK", "Stofdepotet", "SySiden"],
        "local_terms": [
            "stof metervare", "bomuldsstof", "hørrestof", "quiltestof",
            "jerseystof", "møbelstof",
        ],
        "google_keywords": [
            "stof metervare", "bomuldsstof", "quilte stof", "jerseystof",
            "hør stof", "møbelstof", "sy stof",
        ],
    },
    "PL": {
        "name": "Poland",
        "flag": "\U0001F1F5\U0001F1F1",
        "currency": "PLN",
        "geo": "PL",
        "region": "eastern",
        "local_marketplaces": ["Dresówka", "TkaninySklep", "Allegro", "Tkaniny.net"],
        "local_terms": [
            "tkanina bawełniana", "tkanina na metry", "dresówka",
            "dzianina", "tkanina tapicerska", "tkanina lniana",
        ],
        "google_keywords": [
            "tkanina na metry", "tkanina bawełniana", "dresówka",
            "dzianina", "tkanina tapicerska", "tkanina lniana",
        ],
    },
    "CZ": {
        "name": "Czech Republic",
        "flag": "\U0001F1E8\U0001F1FF",
        "currency": "CZK",
        "geo": "CZ",
        "region": "eastern",
        "local_marketplaces": ["Textilní galerie", "Metrax", "Stoklasa"],
        "local_terms": [
            "látka metráž", "bavlněná látka", "lněná látka",
            "úplet", "dekorační látka", "čalounická látka",
        ],
        "google_keywords": [
            "látka metráž", "bavlněná látka", "úplet",
            "dekorační látka", "lněná látka", "patchwork látka",
        ],
    },
    "NO": {
        "name": "Norway",
        "flag": "\U0001F1F3\U0001F1F4",
        "currency": "NOK",
        "geo": "NO",
        "region": "nordic",
        "local_marketplaces": ["Stoff&Stil NO", "Stoffbutikken", "Sy-Spansen"],
        "local_terms": [
            "stoff metervare", "bomullsstoff", "linstoff", "quiltestoff",
            "jerseystoff", "møbelstoff",
        ],
        "google_keywords": [
            "stoff metervare", "bomullsstoff", "quiltestoff", "jerseystoff",
            "linstoff", "møbelstoff", "sy stoff",
        ],
    },
    "BE": {
        "name": "Belgium",
        "flag": "\U0001F1E7\U0001F1EA",
        "currency": "EUR",
        "geo": "BE",
        "region": "western",
        "local_marketplaces": ["Stoffen.net", "Stof&Stil BE", "Textielstad"],
        "local_terms": [
            "stof per meter", "katoenen stof", "linnen stof",
            "tissu au mètre", "tissu coton", "tissu lin",
        ],
        "google_keywords": [
            "stof per meter", "tissu au mètre", "katoenen stof",
            "linnen stof", "tissu coton", "naaistoffen",
        ],
    },
    "FR": {
        "name": "France",
        "flag": "\U0001F1EB\U0001F1F7",
        "currency": "EUR",
        "geo": "FR",
        "region": "western",
        "local_marketplaces": [
            "Mondial Tissus", "Les Coupons de Saint-Pierre", "Tissus.net",
            "Ma Petite Mercerie", "Tissus Price", "Pretty Mercerie",
            "Bennytex", "Motif Personnel", "Atelier de la Création",
            "Driessen Stoffen FR", "Toto Tissus", "Sacrés Coupons",
        ],
        "local_terms": [
            "tissu au mètre", "tissu coton", "tissu lin", "tissu liberty",
            "toile de jouy", "tissu ameublement", "tissu jersey",
        ],
        "google_keywords": [
            "tissu au mètre", "tissu coton", "tissu lin", "tissu liberty",
            "toile de jouy", "tissu ameublement", "tissu jersey",
        ],
    },
}

# Region groupings for "area" view
EUROPEAN_REGIONS = {
    "nordic": {
        "label": "Scandinavia & Nordics",
        "countries": ["SE", "NO", "DK", "FI"],
    },
    "western": {
        "label": "Western Europe",
        "countries": ["NL", "DE", "BE", "FR"],
    },
    "eastern": {
        "label": "Central/Eastern Europe",
        "countries": ["PL", "CZ"],
    },
}
