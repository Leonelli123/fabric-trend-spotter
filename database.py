"""SQLite database for storing scraped fabric trend data."""

import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            price REAL,
            currency TEXT DEFAULT 'USD',
            favorites INTEGER DEFAULT 0,
            reviews INTEGER DEFAULT 0,
            rating REAL,
            image_url TEXT,
            tags TEXT,  -- JSON array
            segment TEXT DEFAULT 'general',
            country TEXT DEFAULT '',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL,
            term TEXT NOT NULL,
            mention_count INTEGER DEFAULT 0,
            avg_price REAL,
            avg_favorites INTEGER DEFAULT 0,
            source TEXT NOT NULL,
            score REAL DEFAULT 0,
            velocity REAL DEFAULT 0,
            lifecycle TEXT DEFAULT 'unknown',
            segment TEXT DEFAULT 'general',
            country TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS google_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            interest INTEGER,
            date TEXT,
            country TEXT DEFAULT '',
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL,
            category TEXT NOT NULL,
            current_score REAL DEFAULT 0,
            predicted_score REAL DEFAULT 0,
            velocity REAL DEFAULT 0,
            acceleration REAL DEFAULT 0,
            lifecycle TEXT DEFAULT 'emerging',
            confidence REAL DEFAULT 0,
            signals TEXT,  -- JSON: list of signal descriptions
            country TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT NOT NULL,
            category TEXT NOT NULL,
            image_url TEXT NOT NULL,
            source TEXT NOT NULL,
            listing_title TEXT,
            listing_url TEXT,
            price REAL,
            segment TEXT DEFAULT 'general',
            country TEXT DEFAULT '',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
        CREATE INDEX IF NOT EXISTS idx_listings_scraped ON listings(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_listings_segment ON listings(segment);
        CREATE INDEX IF NOT EXISTS idx_listings_country ON listings(country);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date ON trend_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_snapshots_category ON trend_snapshots(category);
        CREATE INDEX IF NOT EXISTS idx_snapshots_segment ON trend_snapshots(segment);
        CREATE INDEX IF NOT EXISTS idx_snapshots_country ON trend_snapshots(country);
        CREATE INDEX IF NOT EXISTS idx_forecasts_term ON forecasts(term);
        CREATE INDEX IF NOT EXISTS idx_forecasts_lifecycle ON forecasts(lifecycle);
        CREATE INDEX IF NOT EXISTS idx_forecasts_country ON forecasts(country);
        CREATE INDEX IF NOT EXISTS idx_images_term ON trend_images(term);
        CREATE INDEX IF NOT EXISTS idx_images_category ON trend_images(category);
    """)
    conn.commit()
    conn.close()


def save_listings(listings):
    """Save a list of listing dicts to the database."""
    conn = get_db()
    for item in listings:
        conn.execute(
            """INSERT INTO listings (source, title, url, price, currency,
               favorites, reviews, rating, image_url, tags, segment, country)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.get("source", ""),
                item.get("title", ""),
                item.get("url", ""),
                item.get("price"),
                item.get("currency", "USD"),
                item.get("favorites", 0),
                item.get("reviews", 0),
                item.get("rating"),
                item.get("image_url", ""),
                json.dumps(item.get("tags", [])),
                item.get("segment", "general"),
                item.get("country", ""),
            ),
        )
    conn.commit()
    conn.close()


def save_trend_snapshot(snapshots):
    """Save trend analysis snapshots."""
    conn = get_db()
    for snap in snapshots:
        conn.execute(
            """INSERT INTO trend_snapshots
               (category, term, mention_count, avg_price, avg_favorites,
                source, score, velocity, lifecycle, segment, country)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap["category"],
                snap["term"],
                snap["mention_count"],
                snap.get("avg_price"),
                snap.get("avg_favorites", 0),
                snap["source"],
                snap.get("score", 0),
                snap.get("velocity", 0),
                snap.get("lifecycle", "unknown"),
                snap.get("segment", "general"),
                snap.get("country", ""),
            ),
        )
    conn.commit()
    conn.close()


def save_forecasts(forecasts):
    """Save trend forecasts."""
    conn = get_db()
    conn.execute("DELETE FROM forecasts")
    for f in forecasts:
        conn.execute(
            """INSERT INTO forecasts
               (term, category, current_score, predicted_score, velocity,
                acceleration, lifecycle, confidence, signals)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f["term"],
                f["category"],
                f.get("current_score", 0),
                f.get("predicted_score", 0),
                f.get("velocity", 0),
                f.get("acceleration", 0),
                f.get("lifecycle", "emerging"),
                f.get("confidence", 0),
                json.dumps(f.get("signals", [])),
            ),
        )
    conn.commit()
    conn.close()


def save_trend_images(images):
    """Save trend-associated images."""
    conn = get_db()
    for img in images:
        existing = conn.execute(
            "SELECT id FROM trend_images WHERE image_url = ?",
            (img["image_url"],),
        ).fetchone()
        if existing:
            continue
        conn.execute(
            """INSERT INTO trend_images
               (term, category, image_url, source, listing_title,
                listing_url, price, segment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                img["term"],
                img["category"],
                img["image_url"],
                img.get("source", ""),
                img.get("listing_title", ""),
                img.get("listing_url", ""),
                img.get("price"),
                img.get("segment", "general"),
            ),
        )
    conn.commit()
    conn.close()


def get_latest_trends(category=None, segment=None, country=None, limit=20):
    """Get the most recent trend snapshots."""
    conn = get_db()
    query = """
        SELECT t.* FROM trend_snapshots t
        INNER JOIN (
            SELECT MAX(snapshot_date) as max_date FROM trend_snapshots
        ) latest ON DATE(t.snapshot_date) = DATE(latest.max_date)
        WHERE 1=1
    """
    params = []
    if category:
        query += " AND t.category = ?"
        params.append(category)
    if segment:
        query += " AND t.segment = ?"
        params.append(segment)
    if country is not None:
        query += " AND t.country = ?"
        params.append(country)
    query += " ORDER BY t.score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trend_history(term, days=30):
    """Get trend score history for a specific term."""
    conn = get_db()
    rows = conn.execute(
        """SELECT term, score, mention_count, velocity, lifecycle, snapshot_date
           FROM trend_snapshots
           WHERE term = ? AND snapshot_date >= datetime('now', ?)
           ORDER BY snapshot_date""",
        (term, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_listings(source=None, segment=None, limit=50):
    """Get recent listings, optionally filtered by source and segment."""
    conn = get_db()
    query = "SELECT * FROM listings WHERE 1=1"
    params = []
    if source:
        query += " AND source = ?"
        params.append(source)
    if segment:
        query += " AND segment = ?"
        params.append(segment)
    query += " ORDER BY scraped_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_forecasts(category=None, lifecycle=None, limit=30):
    """Get current forecasts."""
    conn = get_db()
    query = "SELECT * FROM forecasts WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if lifecycle:
        query += " AND lifecycle = ?"
        params.append(lifecycle)
    query += " ORDER BY predicted_score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trend_images(term=None, category=None, segment=None, limit=30):
    """Get images associated with trends."""
    conn = get_db()
    query = "SELECT * FROM trend_images WHERE 1=1"
    params = []
    if term:
        query += " AND term = ?"
        params.append(term)
    if category:
        query += " AND category = ?"
        params.append(category)
    if segment:
        query += " AND segment = ?"
        params.append(segment)
    query += " ORDER BY added_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scrape_stats():
    """Get statistics about data collection."""
    conn = get_db()
    stats = {}
    for source in ["etsy", "amazon", "spoonflower", "pinterest", "seed", "eu_seed"]:
        row = conn.execute(
            """SELECT COUNT(*) as count, MAX(scraped_at) as last_scrape
               FROM listings WHERE source = ?""",
            (source,),
        ).fetchone()
        stats[source] = dict(row)
    row = conn.execute("SELECT COUNT(*) as count FROM trend_snapshots").fetchone()
    stats["total_snapshots"] = row["count"]
    row = conn.execute("SELECT COUNT(*) as count FROM trend_images").fetchone()
    stats["total_images"] = row["count"]
    row = conn.execute("SELECT COUNT(*) as count FROM forecasts").fetchone()
    stats["total_forecasts"] = row["count"]
    # European country stats
    eu_stats = {}
    rows = conn.execute(
        """SELECT country, COUNT(*) as count FROM listings
           WHERE country != '' GROUP BY country"""
    ).fetchall()
    for row in rows:
        eu_stats[row["country"]] = row["count"]
    stats["eu_countries"] = eu_stats
    conn.close()
    return stats
