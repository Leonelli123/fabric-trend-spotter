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
    # Added: commonly searched/stocked fabrics
    "bamboo", "hemp", "tencel", "viscose", "spandex", "lycra",
    "nylon", "lace", "terry", "corduroy", "chenille", "burlap",
    "faux leather", "organic cotton", "cotton linen",
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

# Style/aesthetic movements - these drive 30-50% of purchasing decisions
# and are the strongest leading indicators for what fabrics to stock.
STYLE_TERMS = [
    # Current major aesthetics (2024-2026)
    "cottagecore", "quiet luxury", "minimalist", "maximalist",
    "bohemian", "scandinavian", "coastal", "farmhouse",
    # Rising aesthetics
    "dopamine dressing", "dark academia", "grandmillennial",
    "y2k", "retro", "mod", "art deco",
    # Sustainability movement (huge in Scandinavia)
    "organic", "sustainable", "eco", "natural",
    "deadstock", "upcycled", "recycled",
    # Craft-specific aesthetics
    "handmade", "artisan", "folk", "heritage",
    "japandi", "wabi sabi",
    # Visual mood
    "bold", "vivid", "muted", "earthy", "romantic",
    "whimsical", "elegant", "rustic", "modern",
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

# Trend lifecycle thresholds - used by forecaster.py _classify_lifecycle()
# These are the SINGLE SOURCE OF TRUTH for lifecycle classification.
LIFECYCLE_THRESHOLDS = {
    "emerging": {"min_velocity": 0.15, "max_score": 35},
    "rising": {"min_velocity": 0.08, "min_score": 10, "max_score": 65},
    "peak": {"min_score": 50, "max_velocity": 0.08},
    "declining": {"max_velocity": -0.05},
    "stable": {"min_score": 15, "max_velocity": 0.08, "min_velocity": -0.05},
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
            "Textielstad", "De Stoffenkraam", "Hoofs Stoffen",
            "De Stoffenkoning", "Royal Look", "Stoffenland",
            "De Lappenkraam", "Bottger", "Selfmade NL",
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
            "Stoffe.de", "Snaply", "Stoffe Hemmers", "Buttinette",
            "Stoffkontor", "Stoffmonster", "Schnuckidu",
            "Selfmade DE", "Swafing", "Stofferia",
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
        "local_marketplaces": [
            "Ernst Textil", "Tyg.se", "Skapamer", "Selfmade SE",
            "Tygverket", "Nordisk Textil",
        ],
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
        "local_marketplaces": [
            "Eurokangas", "Kankaita.com", "Selfmade FI",
            "Ottobre", "FabriKing",
        ],
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
        "local_marketplaces": [
            "Selfmade DK", "Stofdepotet", "SySiden", "Stof2000",
            "G&M Textiles", "Jydsk Stoflager",
        ],
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
        "local_marketplaces": [
            "Dresowka.pl", "Textilmar", "Popcouture",
            "CottonStories", "Cottye", "Ultramaszyna", "SuperTkaniny",
        ],
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
        "local_marketplaces": [
            "Stoklasa", "Textilni Galerie", "Metrax",
            "Latky-eshop", "Dumlatek",
        ],
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
        "local_marketplaces": [
            "Selfmade NO", "Stoffbutikken", "Sy-Spansen",
            "Panduro NO", "Stoff og Stil",
        ],
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
        "local_marketplaces": [
            "Stragier", "Stoffen.net", "Selfmade BE",
            "Tissus du Chien Vert",
        ],
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
            "Mondial Tissus", "Tissus des Ursules", "Ma Petite Mercerie",
            "Mercerine", "Tissus.net", "Made in Tissus",
            "Stragier", "Tissus Ellen",
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

# --------------------------------------------------------------------------
# Verified European Shop Database
# Methodology: Each shop verified via web research. Categorized by role:
#   retailer  — shows what's selling at volume (scrape bestsellers)
#   brand     — sets trends (scrape new collections)
#   wholesaler — shows B2B demand (professional buying patterns)
# --------------------------------------------------------------------------

EU_SHOPS = {
    # === PHASE 1: Highest-impact shops (one scraper each covers the most ground) ===
    "selfmade": {
        "name": "Selfmade (Stoff & Stil)",
        "base_url": "https://selfmade.com",
        "countries": ["DK", "DE", "NO", "SE", "FI", "BE", "NL"],
        "locale_paths": {
            "DK": "/da-dk", "DE": "/de-de", "NO": "/nb-no", "SE": "/sv-se",
            "FI": "/fi-fi", "BE": "/nl-be", "NL": "/nl-nl",
        },
        "role": "retailer",
        "priority": 1,
        "note": "Scandinavian chain — one scraper covers 7 markets",
    },
    "stoffe_de": {
        "name": "Stoffe.de",
        "base_url": "https://www.stoffe.de",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 1,
        "note": "Largest DE, Shopware-based (store-api likely). Sister of Tyg.se",
    },
    "snaply": {
        "name": "Snaply",
        "base_url": "https://www.snaply.de",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 1,
        "note": "15k+ fabrics. Has /stoffe/bestseller/ and /stoffe/sale/",
    },
    "textielstad": {
        "name": "Textielstad",
        "base_url": "https://www.textielstad.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 1,
        "note": "Largest NL. 10k+ fabrics. Good category structure",
    },
    "mondial_tissus": {
        "name": "Mondial Tissus",
        "base_url": "https://www.mondialtissus.fr",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 1,
        "note": "100+ stores, largest French fabric chain",
    },
    "dresowka": {
        "name": "Dresowka.pl",
        "base_url": "https://www.dresowka.pl",
        "countries": ["PL"],
        "role": "retailer",
        "priority": 1,
        "note": "Largest PL, strong in jersey/french terry. Has English site",
    },
    "eurokangas": {
        "name": "Eurokangas",
        "base_url": "https://www.eurokangas.fi",
        "countries": ["FI"],
        "role": "retailer",
        "priority": 1,
        "note": "Dominant Finnish market. 30+ physical stores",
    },
    "ernst_textil": {
        "name": "Ernst Textil",
        "base_url": "https://www.ernsttextil.se",
        "countries": ["SE"],
        "role": "retailer",
        "priority": 1,
        "note": "Largest SE with own jersey prints (BY ERNST collection)",
    },

    # === DE retailers (Phase 2) ===
    "stoffe_hemmers": {
        "name": "Stoffe Hemmers",
        "base_url": "https://www.stoffe-hemmers.de",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 2,
        "note": "8k+ fabrics, 35+ years, strong community",
    },
    "buttinette": {
        "name": "Buttinette",
        "base_url": "https://basteln-de.buttinette.com",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 2,
        "note": "Large craft+fabric chain, exclusive designs. Also in FR",
    },
    "stoffkontor": {
        "name": "Stoffkontor",
        "base_url": "https://www.stoffkontor.eu",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 2,
        "note": "10k+ fabrics, also serves schools/institutions",
    },
    "stoffmonster": {
        "name": "Stoffmonster",
        "base_url": "https://www.stoffmonster.net",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 2,
        "note": "Swafing specialist. Stoffmarkt Holland crossover",
    },
    "schnuckidu": {
        "name": "Schnuckidu",
        "base_url": "https://www.schnuckidu.com",
        "countries": ["DE"],
        "role": "retailer",
        "priority": 2,
        "note": "Curated jersey/french terry specialist. Kids/panel focus",
    },

    # === NL retailers (Phase 2) ===
    "destoffenkraam": {
        "name": "De Stoffenkraam",
        "base_url": "https://www.destoffenkraam.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Excellent reviews, sells to DE too",
    },
    "hoofs_stoffen": {
        "name": "Hoofs Stoffen",
        "base_url": "https://www.hoofs-stoffen.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Rating 8.8/10. Wholesale from 10m+",
    },
    "stoffenkoning": {
        "name": "De Stoffenkoning",
        "base_url": "https://www.stoffenkoning.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Physical + online + market stalls",
    },
    "royallook": {
        "name": "Royal Look",
        "base_url": "https://www.royallook.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Tricot specialist, budget segment. Bulk discount 10m+",
    },
    "stoffenland": {
        "name": "Stoffenland",
        "base_url": "https://www.stoffenland.com",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "B2B quote system, baby/kids tricot",
    },
    "delappenkraam": {
        "name": "De Lappenkraam",
        "base_url": "https://www.delappenkraam.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Unique kids prints. Broderie tricot — emerging niches",
    },
    "bottger": {
        "name": "Bottger",
        "base_url": "https://www.bottger.nl",
        "countries": ["NL"],
        "role": "retailer",
        "priority": 2,
        "note": "Premium. Hilco, Nooteboom, Burda. Seasonal trend pages",
    },

    # === FR retailers (Phase 2) ===
    "tissus_ursules": {
        "name": "Tissus des Ursules",
        "base_url": "https://www.tissusdesursules.fr",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "80 stores, mainstream FR demand",
    },
    "mapetitemercerie": {
        "name": "Ma Petite Mercerie",
        "base_url": "https://www.mapetitemercerie.com",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "30k+ refs, designer patterns (Ikatee, Maison Fauve)",
    },
    "mercerine": {
        "name": "Mercerine",
        "base_url": "https://www.mercerine.com",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "Strong jersey section. YouTube channel",
    },
    "tissus_net": {
        "name": "Tissus.net",
        "base_url": "https://www.tissus.net",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "Same parent as Stoffe.de/Tyg.se — compare DE vs FR",
    },
    "madeintissus": {
        "name": "Made in Tissus",
        "base_url": "https://www.madeintissus.fr",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "Pro textile specialist, OEKO-TEX. Ships Benelux",
    },
    "stragier": {
        "name": "Stragier",
        "base_url": "https://www.stragier.com",
        "countries": ["FR", "BE"],
        "role": "retailer",
        "priority": 2,
        "note": "Since 1935, Liberty, luxury. Pro fashion designers",
    },
    "tissus_ellen": {
        "name": "Tissus Ellen",
        "base_url": "https://www.tissusellen.com",
        "countries": ["FR"],
        "role": "retailer",
        "priority": 2,
        "note": "Troyes, physical + online, 35+ year loyalty",
    },

    # === SE retailers (Phase 2) ===
    "tyg_se": {
        "name": "Tyg.se",
        "base_url": "https://www.tyg.se",
        "countries": ["SE"],
        "role": "retailer",
        "priority": 2,
        "note": "Swedish branch of Stoffe.de. Eco brand Tula",
    },
    "skapamer": {
        "name": "Skapamer",
        "base_url": "https://www.skapamer.se",
        "countries": ["SE"],
        "role": "retailer",
        "priority": 2,
        "note": "Budget-friendly generalist, volume demand",
    },
    "tygverket": {
        "name": "Tygverket",
        "base_url": "https://www.tygverket.se",
        "countries": ["SE"],
        "role": "retailer",
        "priority": 2,
        "note": "Premium: Liberty, Morris & Co, Stig Lindberg",
    },
    "nordisk_textil": {
        "name": "Nordisk Textil",
        "base_url": "https://www.nordisktextil.se",
        "countries": ["SE"],
        "role": "retailer",
        "priority": 2,
        "note": "Carries Almedahls + Arvidssons. Since 2006",
    },

    # === NO retailers ===
    "stoffbutikken": {
        "name": "Stoffbutikken",
        "base_url": "https://www.stoffbutikken.no",
        "countries": ["NO"],
        "role": "retailer",
        "priority": 2,
    },
    "syspansen": {
        "name": "Sy-Spansen",
        "base_url": "https://www.syspansen.no",
        "countries": ["NO"],
        "role": "retailer",
        "priority": 2,
    },

    # === DK retailers ===
    "stofdepotet": {
        "name": "Stofdepotet",
        "base_url": "https://www.stofdepotet.dk",
        "countries": ["DK"],
        "role": "retailer",
        "priority": 2,
    },
    "sysiden": {
        "name": "SySiden",
        "base_url": "https://www.sysiden.dk",
        "countries": ["DK"],
        "role": "retailer",
        "priority": 2,
    },
    "stof2000": {
        "name": "Stof2000",
        "base_url": "https://www.stof2000.dk",
        "countries": ["DK"],
        "role": "retailer",
        "priority": 2,
    },

    # === PL retailers ===
    "textilmar": {
        "name": "Textilmar",
        "base_url": "https://sklep.textilmar.pl",
        "countries": ["PL"],
        "role": "retailer",
        "priority": 2,
    },
    "popcouture": {
        "name": "Popcouture",
        "base_url": "https://www.popcouture.pl",
        "countries": ["PL"],
        "role": "retailer",
        "priority": 2,
        "note": "Curated dresowka specialist",
    },
    "ultramaszyna": {
        "name": "Ultramaszyna",
        "base_url": "https://www.ultramaszyna.com",
        "countries": ["PL"],
        "role": "retailer",
        "priority": 2,
        "note": "Polish-produced fabrics",
    },
    "supertkaniny": {
        "name": "SuperTkaniny",
        "base_url": "https://www.supertkaniny.pl",
        "countries": ["PL"],
        "role": "retailer",
        "priority": 2,
    },

    # === CZ retailers ===
    "stoklasa": {
        "name": "Stoklasa",
        "base_url": "https://www.stoklasa.cz",
        "countries": ["CZ"],
        "role": "retailer",
        "priority": 2,
        "note": "Largest CZ textile retailer. Also SK, PL, HU",
    },

    # === BE retailers ===
    "stoffen_net": {
        "name": "Stoffen.net",
        "base_url": "https://www.stoffen.net",
        "countries": ["BE"],
        "role": "retailer",
        "priority": 2,
    },

    # === FI retailers ===
    "kankaita": {
        "name": "Kankaita.com",
        "base_url": "https://www.kankaita.com",
        "countries": ["FI"],
        "role": "retailer",
        "priority": 2,
        "note": "Jersey/trikoo specialist",
    },
}

# Direct competitors: cotton jersey with digital prints (identical business model)
COMPETITOR_BRANDS = {
    "lillestoff": {
        "name": "Lillestoff",
        "url": "https://www.lillestoff.com",
        "country": "DE",
        "tier": "direct",
        "note": "Organic jersey, GOTS digital prints. Closest competitor",
    },
    "albstoffe": {
        "name": "Albstoffe / Hamburger Liebe",
        "url": "https://www.albstoffe.com",
        "country": "DE",
        "tier": "direct",
        "note": "Bio jersey, jacquard, digital prints. Made in Germany. Premium",
    },
    "seeyouatsix": {
        "name": "See You at Six",
        "url": "https://www.seeyouatsix.com",
        "country": "BE",
        "tier": "direct",
        "note": "Jersey/French terry, trendy prints. Strong social media",
    },
    "paapii": {
        "name": "PaaPii Design",
        "url": "https://www.paapiidesign.com",
        "country": "FI",
        "tier": "direct",
        "note": "Finnish organic jersey, GOTS. Own factory",
    },
    "elvelyckan": {
        "name": "Elvelyckan Design",
        "url": "https://www.elvelyckan.com",
        "country": "SE",
        "tier": "direct",
        "note": "Organic jersey + POD. Licensed prints. Almost identical model",
    },
    "stoffonkel": {
        "name": "Stoffonkel",
        "url": "https://www.stoffonkel.de",
        "country": "DE",
        "tier": "direct",
        "note": "German organic digital print jersey",
    },
    "stenzo": {
        "name": "Stenzo",
        "url": "https://www.stenzo.com",
        "country": "NL",
        "tier": "direct",
        "note": "Dutch digital print jersey, EU-wide distribution",
    },
    "gluenz": {
        "name": "Glunz",
        "url": "https://www.gluenz.com",
        "country": "DE",
        "tier": "direct",
        "note": "German jersey/sweat brand with digital prints",
    },
    # Close competitors (overlap in fabric type or market)
    "arvidssons": {
        "name": "Arvidssons Textil",
        "url": "https://www.arvidssonstextil.se",
        "country": "SE",
        "tier": "close",
        "note": "Swedish design house, 15+ designers. Nordic trendsetter",
    },
    "hilco": {
        "name": "Hilco",
        "url": "https://www.hilco.de",
        "country": "DE",
        "tier": "close",
        "note": "German fabric brand, jersey + woven prints",
    },
    "cpauli": {
        "name": "C.Pauli",
        "url": "https://www.cpauli.com",
        "country": "DE",
        "tier": "close",
        "note": "Organic cotton prints, children's focus",
    },
    "verhees": {
        "name": "Verhees Textiles",
        "url": "https://www.verhees.nl",
        "country": "NL",
        "tier": "close",
        "note": "Dutch wholesale print fabrics. Supplies many EU retailers",
    },
    "swafing": {
        "name": "Swafing",
        "url": "https://www.swafing.de",
        "country": "DE",
        "tier": "close",
        "role": "wholesaler",
        "note": "Major DE wholesaler. Seasonal collections set retail trends",
    },
    "nooteboom": {
        "name": "Nooteboom Textiles",
        "url": "https://www.nooteboom.com",
        "country": "NL",
        "tier": "close",
        "note": "Dutch fabric brand, design-forward",
    },
    "rijs": {
        "name": "Rijs Textiles",
        "url": "https://www.rijstextiles.com",
        "country": "NL",
        "tier": "close",
        "note": "NL wholesale. Digital print jersey, French terry",
    },
    "fabriking": {
        "name": "FabriKing",
        "url": "https://www.fabriking.fi",
        "country": "FI",
        "tier": "close",
        "note": "Finnish stretchy prints for adults",
    },
    # Design references (different product but trend signal)
    "atelierbrunette": {
        "name": "Atelier Brunette",
        "url": "https://www.atelierbrunette.com",
        "country": "FR",
        "tier": "reference",
        "note": "French fabric design. Natural tones. Shows French taste",
    },
    "marimekko": {
        "name": "Marimekko",
        "url": "https://www.marimekko.com",
        "country": "FI",
        "tier": "reference",
        "note": "Finnish icon. Color/pattern choices influence Nordic taste",
    },
}

# Wholesalers that show B2B demand (what retailers are ordering 3-6 months ahead)
EU_WHOLESALERS = {
    "swafing": {
        "name": "Swafing",
        "url": "https://www.swafing.de",
        "country": "DE",
        "note": "Seasonal collections set what appears in retail 3-6 months later",
    },
    "stofferia": {
        "name": "Stofferia",
        "url": "https://www.stofferia.de",
        "country": "DE",
        "note": "B2B wholesale with EU-wide portal. GOTS-certified",
    },
    "gm_textiles": {
        "name": "G&M Textiles (Tyger & Textil)",
        "url": "https://www.tygerochtextil.se",
        "country": "DK",
        "note": "Aarhus-based B2B. Sources from DE, NL, IT, TR. Wholesale rolls",
    },
    "cottonstories": {
        "name": "CottonStories (CoStories)",
        "url": "https://www.costories.com",
        "country": "PL",
        "note": "Knit MANUFACTURER in Lodz. Produces dresowka in bamboo, cotton, organic",
    },
    "cottye": {
        "name": "Cottye",
        "url": "https://www.cottye.pl",
        "country": "PL",
        "note": "Fabric wholesaler. TUV + OEKO-TEX certified",
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
