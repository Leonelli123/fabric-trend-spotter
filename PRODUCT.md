# Fabric Trend Spotter — Product Document & Architecture

## What This Tool Does

Fabric Trend Spotter is a **real-time fabric trend intelligence platform** built for fabric business owners, buyers, designers, marketing teams, and sales professionals. It collects data from multiple online marketplaces, social platforms, search engines, and industry sources — then analyzes, scores, forecasts, and presents actionable recommendations tailored to each business role.

**Primary user:** A Scandinavian fabric business (retail + wholesale + design) expanding across Europe, covering all aesthetics from cottagecore to quiet luxury to bold maximalist.

**Core value proposition:** Instead of guessing what fabrics, patterns, colors, and styles to stock, design, or promote — this tool tells you based on cross-platform data, Google search demand, social visual trends, and industry forecasting signals.

---

## The Situation / Problem It Solves

Running a fabric business means making decisions months in advance:
- **Buyers** must order fabrics 2-6 months before customers want them
- **Designers** need to know which color palettes and styles will resonate next season
- **Marketing** needs to align campaigns with what people are actually searching for
- **Sales teams** need to know what to push hard now vs. what's declining
- **CEOs** need a strategic overview: where is the market heading?

Traditional approach: gut feeling, trade show visits, following competitors, scrolling Instagram. This is slow, biased, and misses emerging trends.

**Fabric Trend Spotter replaces guesswork with data-driven intelligence** by:
1. Scraping real marketplace listings (Etsy, Amazon, Spoonflower) to see what sellers are offering and what buyers are engaging with
2. Analyzing Pinterest for visual trend signals (what crafters and designers are saving/pinning)
3. Pulling Google Trends data to detect search demand before it hits stores
4. Scraping industry trend reports from authoritative sources (Pantone, fashion publications, textile trade shows)
5. Running everything through a scoring algorithm and forecasting engine
6. Presenting role-specific actionable recommendations

---

## Full Project Structure

```
fabric-trend-spotter/
│
├── app.py                          # Flask web application (656 lines)
│   ├── Routes: /, /api/scrape, /api/trends, /api/listings, /api/forecasts,
│   │          /api/images, /api/european-trends, /api/pinterest-trends, /api/status
│   ├── _run_scrape()               # Orchestrates the full data pipeline
│   └── _build_action_board()       # Generates role-specific recommendations
│
├── config.py                       # All configuration constants (364 lines)
│   ├── FABRIC_TYPES (46 terms)     # Cotton, linen, silk, bamboo, tencel, etc.
│   ├── PATTERN_TYPES (30 terms)    # Floral, geometric, stripe, toile, etc.
│   ├── COLOR_TERMS (34 terms)      # Sage green, dusty rose, terracotta, etc.
│   ├── STYLE_TERMS (37 terms)      # Cottagecore, quiet luxury, scandinavian, etc.
│   ├── SEGMENTS                    # Quilting, Apparel, Home Decor, Cosplay, Craft
│   ├── LIFECYCLE_THRESHOLDS        # Emerging/rising/peak/declining/stable rules
│   ├── EUROPEAN_COUNTRIES          # 10 countries: SE, NO, DK, FI, NL, DE, BE, FR, PL, CZ
│   └── EUROPEAN_REGIONS            # Nordic, Western Europe, Central/Eastern Europe
│
├── database.py                     # SQLite database layer (343 lines)
│   ├── Tables: listings, trend_snapshots, trend_images, forecasts
│   ├── save_listings()             # Stores scraped marketplace data
│   ├── save_trend_snapshot()       # Stores analyzed trend scores over time
│   ├── save_forecasts()            # Stores lifecycle predictions
│   ├── get_latest_trends()         # Retrieves current trend rankings
│   ├── get_trend_history()         # Retrieves historical scores for velocity calc
│   └── get_trend_images()          # Retrieves gallery images by term/category
│
├── analysis/                       # Analysis & forecasting engine
│   ├── __init__.py                 # Exports: analyze_trends, analyze_european_trends, run_forecasts
│   │
│   ├── engine.py                   # Core trend analysis (745 lines)
│   │   ├── analyze_trends()        # Main pipeline: filter → count → enrich → validate → score
│   │   ├── analyze_european_trends()  # Per-country + per-region EU analysis
│   │   ├── _count_term_occurrences()  # Quality-weighted term counting
│   │   ├── _enrich_with_google()      # Add Google Trends data to each term
│   │   ├── _enrich_with_trend_reports() # Add industry authority signals
│   │   ├── _calculate_scores()     # Composite scoring algorithm (100-point scale)
│   │   ├── _generate_insights()    # Human-readable insight cards
│   │   ├── _classify_segments()    # Assign listings to market segments
│   │   └── _extract_trend_images() # Build visual gallery from quality listings
│   │
│   ├── forecaster.py               # Trend forecasting (401 lines)
│   │   ├── run_forecasts()         # Generate predictions for all terms
│   │   ├── _calculate_velocity()   # Rate of score change (weighted smoothing)
│   │   ├── _calculate_acceleration() # Is growth speeding up or slowing?
│   │   ├── _detect_signals()       # Cross-platform convergence detection
│   │   ├── _classify_lifecycle()   # Emerging → Rising → Peak → Declining → Stable
│   │   ├── _predict_score()        # 30-day score prediction
│   │   └── _calculate_confidence() # Forecast confidence (0-95%)
│   │
│   └── quality.py                  # Data quality & validation (320 lines)
│       ├── score_listing_quality()     # Per-listing credibility (0.0-1.0)
│       ├── filter_listings()           # Remove spam, duplicates, outliers
│       ├── validate_trend()            # Minimum evidence thresholds
│       ├── weighted_average()          # Quality-weighted statistics
│       ├── estimate_unique_sellers()   # Seller diversity from URL patterns
│       └── remove_price_outliers()     # IQR-based price filtering
│
├── scrapers/                       # Data collection layer
│   ├── __init__.py                 # Exports all scraper functions
│   │
│   ├── etsy.py                     # Etsy marketplace scraper (187 lines)
│   │   └── scrape_etsy()           # Scrapes fabric listings with engagement data
│   │
│   ├── amazon.py                   # Amazon marketplace scraper (123 lines)
│   │   └── scrape_amazon()         # Scrapes fabric product listings
│   │
│   ├── spoonflower.py              # Spoonflower Pythias API scraper (190 lines)
│   │   ├── scrape_spoonflower()    # Fetches bestselling designs via internal API
│   │   ├── _fetch_designs()        # Calls pythias.spoonflower.com/search/v3/designs
│   │   ├── _design_to_listing()    # Converts API response to standard format
│   │   └── _extract_tags()         # Extracts trend terms + Spoonflower themes
│   │   # Topics: animals, geometric, abstract, stripes, plaid, holiday,
│   │   #         vintage, nature, floral, botanical
│   │
│   ├── pinterest.py                # Pinterest visual trend scraper (359 lines)
│   │   ├── scrape_pinterest()      # Fetches pins via internal search API
│   │   └── analyze_pinterest_data() # Aggregates fabric/pattern/color/style signals
│   │
│   ├── google_trends.py            # Google Trends integration (247 lines)
│   │   ├── fetch_google_trends()   # 60+ fabric keywords via pytrends
│   │   └── fetch_european_trends() # Local-language keywords per EU country
│   │   # Batches of 5 keywords with exponential backoff
│   │
│   ├── trend_reports.py            # Industry trend report scraper (290 lines)
│   │   └── fetch_trend_reports()   # Scrapes Pantone, fashion publications,
│   │                               # textile trade show reports
│   │   # Authority-weighted scoring (Pantone > blogs)
│   │
│   ├── seed_data.py                # Curated baseline data (132 lines)
│   │   └── get_seed_listings()     # 81 hand-curated trend-setter listings
│   │   # Includes: Scandinavian styles, sustainability, Pantone 2025-2026,
│   │   # trending fabrics (bamboo, tencel), stripe variants
│   │
│   ├── european_seed_data.py       # European market seed data (224 lines)
│   │   └── get_european_seed_listings()  # Listings tagged per EU country
│   │   # Covers 10 countries with local marketplace names and terms
│   │
│   ├── base.py                     # Base scraper utilities (59 lines)
│   │   └── Shared HTTP helpers, rate limiting
│   │
│   └── instagram.py                # [DEPRECATED] Replaced by Pinterest
│
├── templates/
│   ├── dashboard.html              # Main dashboard template (989 lines)
│   │   ├── Action Board section    # Role-specific recommendations (top of page)
│   │   ├── Insights cards          # AI-generated trend insights
│   │   ├── Trend charts            # 4-column: Fabrics, Patterns, Colors, Styles
│   │   ├── Forecast table          # Lifecycle predictions with confidence %
│   │   ├── Visual gallery          # Filterable trend image grid
│   │   ├── Segment analysis        # Quilting, Apparel, Home Decor, etc.
│   │   ├── European markets        # Per-country and per-region trends
│   │   ├── Pinterest signals       # Social/visual trend indicators
│   │   └── Raw listings browser    # Filterable listing cards
│   │
│   ├── privacy.html                # Privacy policy
│   ├── terms.html                  # Terms of service
│   └── data_deletion_status.html   # Data deletion status page
│
├── static/
│   ├── css/style.css               # Dashboard styles (1247 lines)
│   │   ├── Dark theme with accent colors
│   │   ├── Action board cards (order/sample/reduce/promote/premium)
│   │   ├── Seasonal color chips and fabric chips
│   │   ├── Horizon indicators (macro/seasonal/short-term)
│   │   ├── Responsive 4-column chart grid
│   │   └── Gallery, tabs, badges, confidence indicators
│   │
│   └── js/dashboard.js             # Dashboard interactivity (239 lines)
│       ├── initCharts()            # Chart.js bar charts for all 4 dimensions
│       ├── triggerScrape()         # Initiates data refresh
│       ├── pollStatus()            # Polls scrape progress
│       ├── switchTab/switchRole/switchEU/switchSegment()  # Tab navigation
│       ├── filterGallery()         # Visual gallery category filter
│       ├── loadListings()          # Lazy-load raw listing cards
│       └── IntersectionObserver    # Auto-load listings on scroll
│
├── data/
│   └── trends.db                   # SQLite database (auto-created)
│
├── requirements.txt                # Python dependencies
│   ├── flask==3.1.0
│   ├── gunicorn==23.0.0
│   ├── requests==2.32.3
│   ├── beautifulsoup4==4.12.3
│   ├── apscheduler==3.10.4
│   └── pytrends==4.9.2
│
├── gunicorn_config.py              # Gunicorn production settings
├── render.yaml                     # Render.com deployment config
├── .python-version                 # Python 3.11.0
└── .gitignore
```

---

## How the Data Pipeline Works

### Step 1: Data Collection (scrapers/)
When "Refresh Data" is clicked, `_run_scrape()` executes in a background thread:

1. **Seed Data** — Always loaded first as baseline (81 curated listings). Ensures the dashboard is never empty even if all live scrapers fail.

2. **Live Marketplace Scrapers** — Each runs independently, failures are graceful:
   - **Etsy**: Fabric listings with prices, favorites, reviews, ratings
   - **Amazon**: Product listings with reviews, ratings, prices
   - **Spoonflower**: Bestselling designs via their internal Pythias API (favorites, order counts, designer tags, thumbnails)
   - **Pinterest**: Fabric-related pins via internal search API (saves/repins as engagement)

3. **Google Trends** — Fetches search interest for 60+ fabric-related keywords in batches of 5 with exponential backoff. Returns trending_up/trending_down signals and interest scores (0-100).

4. **Industry Trend Reports** — Scrapes authoritative sources (Pantone, fashion publications, trade show reports). Extracts signals with authority-weighted scoring.

5. **European Market Data** — Loads EU seed listings for 10 countries with local marketplace names, then fetches EU Google Trends (local-language keywords per country).

### Step 2: Quality Filtering (analysis/quality.py)
Before analysis, all listings pass through quality gates:
- **Deduplication**: Same title + source = duplicate removed
- **Spam removal**: Titles < 5 chars, prices outside $0-$500
- **Quality scoring**: Each listing gets a 0.0-1.0 credibility score based on reviews, favorites, rating, price sanity, title quality, images

### Step 3: Trend Analysis (analysis/engine.py)
1. **Term counting**: For each of the 147 tracked terms (46 fabrics + 30 patterns + 34 colors + 37 styles), count how many quality listings mention it
2. **Quality weighting**: Prices, favorites, and counts are weighted by listing credibility
3. **Google enrichment**: Attach Google Trends interest scores and trending direction
4. **Industry enrichment**: Attach authority signals from trend reports
5. **Validation**: Each term must meet minimum evidence thresholds to be called a "trend"
6. **Composite scoring** (out of 100 points):
   - Search demand: 25 pts (Google Trends — leading indicator)
   - Marketplace presence: 20 pts (listing count, quality-weighted)
   - Momentum: 15 pts (Google trending up, Pinterest presence)
   - Source diversity: 12 pts (multi-platform = real trend)
   - Community validation: 10 pts (favorites/engagement)
   - Seller diversity: 8 pts (multiple independent sellers)
   - Industry signals: 10 pts (Pantone, fashion week, trade reports)
7. **Confidence penalty**: Weak evidence → score dampened (verified: 1.0x, strong: 0.9x, moderate: 0.75x, weak: 0.5x)

### Step 4: Forecasting (analysis/forecaster.py)
For every validated trend term:
1. **Velocity**: Rate of score change over time (weighted recent vs. old)
2. **Acceleration**: Is growth speeding up or slowing down?
3. **Signal detection**: Cross-platform convergence, demand gaps, engagement ratios, price premiums, Pinterest visual signals
4. **Lifecycle classification**:
   - **Emerging**: Low score + high velocity → order samples now
   - **Rising**: Growing score + positive velocity → stock up now
   - **Peak**: High score + velocity slowing → push hard before decline
   - **Declining**: Score dropping → stop reordering, sell through
   - **Stable**: Consistent demand → evergreen, always stock
5. **30-day prediction**: Projects future score using velocity + acceleration + signals + lifecycle modifiers
6. **Confidence**: 0-95% based on history depth, signal count, source diversity, data quality

### Step 5: Action Board (app.py → _build_action_board)
Synthesizes all analysis into role-specific recommendations:

**Buyer / Indkøber:**
- "ORDER" cards: Rising trends → stock these now (with velocity %, score trajectory, confidence)
- "SAMPLE" cards: Emerging trends → order samples, plan production in 60 days
- "REDUCE" cards: Declining trends → don't reorder, sell through remaining

**Designer:**
- Color palette: Current top 6 trending colors
- Pattern directions: Rising/emerging patterns to design around
- Style directions: Dominant aesthetics driving consumer preference

**Marketing:**
- Content themes: What to create content about (with Google demand data)
- Campaign aesthetics: Which visual styles to align branding with

**Sales:**
- "PROMOTE" cards: Peak trends → push hard now before decline
- "UPSELL" cards: Rising trends for cross-sell opportunities
- Premium opportunities: High-price terms for premium positioning

**CEO / Strategic:**
- Market summary: Total trends tracked, counts by lifecycle stage
- Top term per category (fabric, pattern, color, style)

**Trend Horizons:**
- Macro (6-12 months): Sustainability, organic, minimalist, natural — long-term shifts
- Seasonal: Auto-detects current season → recommends colors and fabrics
- Short-term (1-3 months): Fast-moving viral trends with high velocity

### Step 6: European Analysis
Runs the full analysis pipeline per country and per region:
- 10 countries: Sweden, Norway, Denmark, Finland, Netherlands, Germany, Belgium, France, Poland, Czech Republic
- 3 regions: Scandinavia & Nordics, Western Europe, Central/Eastern Europe
- Each gets: fabric/pattern/color rankings, top trends, local marketplace names
- Country-specific Google Trends in local languages

---

## Dashboard Sections (What the User Sees)

1. **Action Board** — Role tabs at the very top. Switch between Buyer, Designer, Marketing, Sales, Seasonal. Each shows prioritized action cards with color-coded urgency.

2. **CEO Summary Bar** — Lifecycle counts (emerging/rising/peak/declining), top term per category.

3. **Trend Insights** — AI-generated insight cards: Rising trends, Hottest overall, Niche opportunities, Premium segments. Each with confidence tier and sample images.

4. **Trend Forecasts** — Table of all forecasted terms with lifecycle badges, velocity arrows, predicted scores, confidence percentages.

5. **Trend Charts** — 4-column bar charts: Fabrics, Patterns, Colors, Styles. Top 10 scored terms each.

6. **Visual Gallery** — Filterable grid of trend images from scraped listings. Filter by: All, Fabric, Pattern, Color, Style.

7. **Market Segments** — Tabs for Quilting, Apparel, Home Decor, Cosplay, Craft. Each shows segment-specific trend rankings.

8. **European Markets** — Tabs for each country and region. Shows local trends, local marketplace names, regional differences.

9. **Pinterest Signals** — Social/visual trend data from Pinterest analysis.

10. **Raw Data Browser** — Scrollable listing cards with source badges, prices, favorites, reviews, tags. Filter by source.

---

## Data Sources Summary

| Source | Type | What It Provides | Signal Strength |
|--------|------|-------------------|-----------------|
| **Google Trends** | Search demand | Interest scores (0-100), trending direction | Leading (3-6 months ahead) |
| **Pinterest** | Visual/social | Pin saves, repins, visual trend momentum | Leading (2-3 months ahead) |
| **Industry Reports** | Authority | Pantone picks, fashion week reports, trade shows | Leading (6-12 months ahead) |
| **Spoonflower** | Marketplace | Bestselling designs, favorites, orders, tags | Current (real-time demand) |
| **Etsy** | Marketplace | Listings, prices, favorites, reviews, ratings | Current (real-time demand) |
| **Amazon** | Marketplace | Product listings, reviews, ratings, prices | Lagging (mass-market) |
| **Seed Data** | Curated | 81 hand-curated trend-setter listings | Baseline / expert input |
| **EU Seed Data** | Curated | European marketplace data per country | Baseline / market context |

---

## Technology Stack

- **Backend**: Python 3.11, Flask 3.1
- **Database**: SQLite (file-based, zero config)
- **Frontend**: Vanilla HTML/CSS/JS + Chart.js
- **Scraping**: requests, BeautifulSoup4, pytrends
- **Deployment**: Render.com (free tier), gunicorn
- **No external AI APIs required** — all analysis is algorithmic

---

## What Makes This Different

1. **Multi-source triangulation**: A trend must appear on multiple platforms to score high. Single-source signals get dampened.
2. **Quality-weighted everything**: A listing with 100 reviews counts more than one with zero. Prices are outlier-filtered. Duplicates are removed.
3. **Leading indicators first**: Google search demand and industry reports are weighted 2x higher than marketplace presence because they predict trends before they peak.
4. **Role-specific actionability**: Not just "here are the trends" but "here's what YOU should do about it based on YOUR role."
5. **European market depth**: 10 countries with local-language data, local marketplace names, regional groupings.
6. **Lifecycle awareness**: Tells you whether a trend is emerging (invest early), peak (push now), or declining (stop ordering).
7. **Confidence transparency**: Every data point has a confidence tier (verified/strong/moderate/weak) so you know how much to trust it.

---

## Deployment

Deployed on Render.com:
- Free tier web service
- Python 3.11 runtime
- gunicorn production server
- SQLite stored in /tmp (ephemeral on Render free tier) or ./data/ (local)
- Environment variables: SECRET_KEY (auto-generated), ETSY_API_KEY (optional)
- Data refreshes on demand via dashboard button

---

## Total Codebase

- **~5,000 lines of Python** (backend + scrapers + analysis + forecasting)
- **~2,900 lines of HTML/CSS/JS** (dashboard frontend)
- **~7,900 lines total**
- **147 tracked trend terms** across 4 dimensions
- **10 European countries** with local-language coverage
- **5 market segments** (quilting, apparel, home decor, cosplay, craft)
- **5 business roles** (buyer, designer, marketing, sales, CEO)
- **3 trend horizons** (macro, seasonal, short-term)
