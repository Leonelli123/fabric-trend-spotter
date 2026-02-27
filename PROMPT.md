# Fabric Trend Spotter — Continuation Prompt

Use this prompt when starting a new session with an AI assistant to continue development on this project. It provides full context so the assistant can pick up exactly where you left off.

---

## The Situation

I'm building a **real-time fabric trend intelligence tool** for my fabric business. I operate in Scandinavia (primary market) expanding across Europe — covering retail, wholesale, and design. We stock all aesthetics: cottagecore, quiet luxury, bold/maximalist, Scandinavian minimalism, and everything in between.

### The Business Problem
In the fabric industry, buying decisions must be made 2-6 months before customers want the product. I need data-driven intelligence to:
- Know which fabrics, patterns, colors, and styles to ORDER now vs. STOP ordering
- Spot emerging trends before competitors
- Understand seasonal color and fabric cycles
- See what's trending on marketplaces, social media, and Google search
- Make different decisions depending on my role: buying, design, marketing, sales, or strategic

### What the Tool Does Today
The tool is a **Flask web application** deployed on Render.com that:

1. **Collects data from 8 sources:**
   - Etsy, Amazon, Spoonflower (marketplace listings with prices, favorites, reviews)
   - Pinterest (visual/social trend signals via internal API)
   - Google Trends (search demand for 60+ fabric keywords, US + 10 EU countries in local languages)
   - Industry trend reports (Pantone, fashion publications, textile trade shows — authority-weighted)
   - Curated seed data (81 US + ~102 EU baseline listings)

2. **Analyzes across 4 dimensions with 147 tracked terms:**
   - Fabric types (46): cotton, linen, silk, bamboo, tencel, velvet, etc.
   - Patterns (30): floral, geometric, stripe, toile, cottagecore, etc.
   - Colors (34): sage green, dusty rose, terracotta, cream, etc.
   - Styles (37): cottagecore, quiet luxury, minimalist, scandinavian, etc.

3. **Scores trends on a 100-point composite scale:**
   - Search demand (25pts) — Google Trends, leading indicator
   - Marketplace presence (20pts) — listing count, quality-weighted
   - Momentum (15pts) — trending direction, Pinterest signals
   - Source diversity (12pts) — multi-platform confirmation
   - Community validation (10pts) — favorites/engagement
   - Seller diversity (8pts) — multiple independent sellers
   - Industry signals (10pts) — Pantone, fashion week, trade reports

4. **Forecasts trend lifecycles:**
   - Emerging → Rising → Peak → Declining → Stable
   - 30-day score predictions with confidence percentages
   - Velocity (rate of change) and acceleration (is growth speeding up?)

5. **Generates role-specific Action Board:**
   - **Buyer/Indkøber**: ORDER (rising trends), SAMPLE (emerging), REDUCE (declining)
   - **Designer**: Color palettes, pattern directions, style aesthetics
   - **Marketing**: Content themes with search demand data, campaign aesthetics
   - **Sales**: PROMOTE (peak trends), UPSELL (rising), premium pricing opportunities
   - **CEO**: Market summary with lifecycle counts, top terms, strategic overview
   - **Seasonal**: Auto-detected season with recommended colors and fabrics
   - **Trend Horizons**: Macro (6-12mo), Seasonal (3-6mo), Short-term (1-3mo)

6. **Covers European markets:**
   - 10 countries: Sweden, Norway, Denmark, Finland, Netherlands, Germany, Belgium, France, Poland, Czech Republic
   - 3 regions: Nordic, Western Europe, Central/Eastern
   - Local-language Google Trends, local marketplace names, native-language seed data

7. **Quality layer prevents noise:**
   - Listings scored 0.0-1.0 for credibility (reviews, favorites, rating, price, title quality)
   - Trends validated with minimum evidence thresholds
   - Confidence tiers: verified, strong, moderate, weak
   - Price outlier removal via IQR method
   - Duplicate detection

### Technology Stack
- Python 3.11, Flask 3.1, SQLite, gunicorn
- Vanilla HTML/CSS/JS + Chart.js (no framework)
- requests, BeautifulSoup4, pytrends
- Deployed on Render.com free tier
- ~7,900 lines of code total

### Project Structure
```
fabric-trend-spotter/
├── app.py                    # Flask app, routes, _run_scrape(), _build_action_board()
├── config.py                 # All constants, term lists, EU countries, segments
├── database.py               # SQLite schema and data access
├── analysis/
│   ├── engine.py             # Trend scoring, insights, EU analysis
│   ├── forecaster.py         # Lifecycle classification, velocity, predictions
│   └── quality.py            # Data quality, validation, outlier removal
├── scrapers/
│   ├── etsy.py               # Etsy marketplace scraper
│   ├── amazon.py             # Amazon marketplace scraper
│   ├── spoonflower.py        # Spoonflower Pythias API (rewritten — internal API)
│   ├── pinterest.py          # Pinterest internal search API
│   ├── google_trends.py      # Google Trends via pytrends (US + EU)
│   ├── trend_reports.py      # Industry source scraper (Pantone, etc.)
│   ├── seed_data.py          # 81 curated US baseline listings
│   ├── european_seed_data.py # ~102 EU seed listings (10 countries)
│   └── base.py               # Shared HTTP utilities
├── templates/
│   └── dashboard.html        # Main dashboard (Action Board, charts, forecasts, gallery, EU, segments)
├── static/
│   ├── css/style.css         # Dark theme dashboard styles
│   └── js/dashboard.js       # Charts, scrape trigger, tab switching, gallery filters
├── requirements.txt          # flask, gunicorn, requests, bs4, apscheduler, pytrends
└── render.yaml               # Render.com deployment config
```

### Key Technical Details
- Spoonflower uses their internal Pythias API: `pythias.spoonflower.com/search/v3/designs`
- Pinterest uses their internal search API: `pinterest.com/resource/BaseSearchResource/get/` with CSRF token
- Google Trends batches 5 keywords at a time with exponential backoff
- Industry reports are authority-weighted (Pantone = 10/10, blogs = 6/10)
- Scoring uses confidence penalties (weak evidence → score dampened)
- EU analysis uses segment-level thresholds (lower bar for smaller country data pools)
- Database uses SQLite WAL mode for concurrent reads
- Forecasts are fully replaced each run (no history tracking yet)

### What Has Been Completed
1. Pinterest scraper (replaced Instagram — which required business API)
2. Spoonflower scraper (rewritten — old HTML scraping broke when site migrated to Next.js)
3. Styles as 4th trend dimension (37 terms)
4. Rebalanced scoring algorithm (search demand weighted highest as leading indicator)
5. Forecaster lifecycle fixes (realistic thresholds, weighted velocity smoothing)
6. Industry trend report scraper (6 authoritative sources + Google News)
7. Expanded seed data (81 US listings with styles, Scandinavian emphasis)
8. Action Board with 5 role tabs + seasonal intelligence + trend horizons
9. Insights cards rendered on dashboard (was generated but never displayed — fixed)
10. European market coverage (10 countries, 3 regions, local-language data)

### Known Gaps / Remaining Work
These are architectural gaps identified but not yet implemented:

1. **EU and Pinterest data is in-memory only** — Lost on server restart. Should be persisted to database.
2. **Forecast history not tracked** — Forecasts are deleted and replaced each run. No way to measure forecast accuracy over time.
3. **No export functionality** — Buyers need CSV/Excel exports for buying meetings and presentations.
4. **No cross-market correlation** — EU vs US trends are analyzed in silos. Should identify trends that are rising in EU but not yet in US (opportunity signal).
5. **No alert/notification system** — Should alert when a trend changes lifecycle (e.g., emerging → rising).
6. **No time-series trend charts** — Dashboard only shows current snapshot, not how trends have moved over time.
7. **No competitor intelligence** — Could track what specific retailers/brands are stocking.
8. **Dashboard could be more visual** — More charts, sparklines in tables, trend arrows.
9. **Scheduled auto-refresh** — apscheduler is in requirements but not wired up for automatic data refresh.
10. **Authentication** — Currently open to anyone with the URL. May need login for business use.

### How to Run Locally
```bash
cd fabric-trend-spotter
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
# Click "Refresh Data" to trigger first scrape
```

### How to Deploy
Push to GitHub, connect to Render.com, it auto-deploys from `render.yaml`.

---

## Instructions for the AI Assistant

When continuing work on this project:

1. **Read PRODUCT.md first** — It has the complete architecture reference.
2. **Read the specific files** before modifying them — the codebase has evolved significantly.
3. **Don't break the quality layer** — All listings must go through `filter_listings()` and trends through `validate_trend()`.
4. **Maintain the scoring balance** — The 100-point composite score was carefully calibrated. Changes to weights affect all downstream forecasts.
5. **Test Spoonflower and Pinterest carefully** — Both use internal APIs that can break if the sites update. Removed topics that return 400 errors.
6. **EU data has lower thresholds** — `is_segment=True` for per-country analysis because the data pools are smaller.
7. **Seed data is the safety net** — It ensures the dashboard always has content. Don't remove it.
8. **The Action Board builds from forecasts** — It depends on lifecycle classification being correct. If you change lifecycle thresholds in `config.py`, test the full pipeline.
9. **Keep the dark theme consistent** — CSS uses `#1a1d2e` background, `#6c63ff` accent, `#e0e0e6` text.
10. **Commit messages should describe the "why"** — Not just "update file" but "Fix Spoonflower scraper: use internal API instead of HTML parsing".
