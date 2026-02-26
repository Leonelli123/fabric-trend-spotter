from scrapers.etsy import scrape_etsy
from scrapers.amazon import scrape_amazon
from scrapers.spoonflower import scrape_spoonflower
from scrapers.google_trends import fetch_google_trends, fetch_european_trends
from scrapers.seed_data import get_seed_listings
from scrapers.european_seed_data import get_european_seed_listings
from scrapers.instagram import (
    fetch_instagram_trends, analyze_instagram_data, is_configured as ig_is_configured,
)
