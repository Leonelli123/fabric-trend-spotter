"""SQLite database for storing scraped fabric trend data."""

import sqlite3
import json
from datetime import datetime
from config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL,  -- 'fabric_type', 'pattern', 'color'
            term TEXT NOT NULL,
            mention_count INTEGER DEFAULT 0,
            avg_price REAL,
            avg_favorites INTEGER DEFAULT 0,
            source TEXT NOT NULL,
            score REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS google_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            interest INTEGER,
            date TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
        CREATE INDEX IF NOT EXISTS idx_listings_scraped ON listings(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date ON trend_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_snapshots_category ON trend_snapshots(category);
    """)
    conn.commit()
    conn.close()


def save_listings(listings):
    """Save a list of listing dicts to the database."""
    conn = get_db()
    for item in listings:
        conn.execute(
            """INSERT INTO listings (source, title, url, price, currency,
               favorites, reviews, rating, image_url, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
               (category, term, mention_count, avg_price, avg_favorites, source, score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                snap["category"],
                snap["term"],
                snap["mention_count"],
                snap.get("avg_price"),
                snap.get("avg_favorites", 0),
                snap["source"],
                snap.get("score", 0),
            ),
        )
    conn.commit()
    conn.close()


def get_latest_trends(category=None, limit=20):
    """Get the most recent trend snapshots."""
    conn = get_db()
    query = """
        SELECT t.* FROM trend_snapshots t
        INNER JOIN (
            SELECT MAX(snapshot_date) as max_date FROM trend_snapshots
        ) latest ON DATE(t.snapshot_date) = DATE(latest.max_date)
    """
    params = []
    if category:
        query += " WHERE t.category = ?"
        params.append(category)
    query += " ORDER BY t.score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trend_history(term, days=30):
    """Get trend score history for a specific term."""
    conn = get_db()
    rows = conn.execute(
        """SELECT term, score, mention_count, snapshot_date
           FROM trend_snapshots
           WHERE term = ? AND snapshot_date >= datetime('now', ?)
           ORDER BY snapshot_date""",
        (term, f"-{days} days"),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_listings(source=None, limit=50):
    """Get recent listings, optionally filtered by source."""
    conn = get_db()
    if source:
        rows = conn.execute(
            "SELECT * FROM listings WHERE source = ? ORDER BY scraped_at DESC LIMIT ?",
            (source, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM listings ORDER BY scraped_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scrape_stats():
    """Get statistics about data collection."""
    conn = get_db()
    stats = {}
    for source in ["etsy", "amazon", "spoonflower"]:
        row = conn.execute(
            """SELECT COUNT(*) as count, MAX(scraped_at) as last_scrape
               FROM listings WHERE source = ?""",
            (source,),
        ).fetchone()
        stats[source] = dict(row)
    row = conn.execute("SELECT COUNT(*) as count FROM trend_snapshots").fetchone()
    stats["total_snapshots"] = row["count"]
    conn.close()
    return stats
