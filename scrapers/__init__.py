from scrapers.etsy import scrape_etsy
from scrapers.amazon import scrape_amazon
from scrapers.spoonflower import scrape_spoonflower
from scrapers.google_trends import fetch_google_trends, fetch_european_trends
from scrapers.seed_data import get_seed_listings
from scrapers.european_seed_data import get_european_seed_listings
from scrapers.pinterest import scrape_pinterest, analyze_pinterest_data
from scrapers.trend_reports import fetch_trend_reports
from scrapers.eu_shops import scrape_eu_shops, scrape_competitors, get_eu_shop_summary
from scrapers.serpapi_source import (
    fetch_serpapi_trends,
    fetch_serpapi_shopping,
    fetch_serpapi_trend_images,
    fetch_serpapi_etsy,
    get_serpapi_summary,
)
