"""Gunicorn configuration for production deployment.

Tuned for Render Free tier (512 MB RAM):
- 1 worker to avoid duplicating in-memory caches across processes
- 2 threads for concurrent request handling within the single worker
- preload_app shares code pages and runs init_db / scheduler once
"""

import multiprocessing
import os

bind = "0.0.0.0:10000"

# On Render Free (512 MB), 1 worker keeps memory under control.
# Each worker duplicates the full in-memory caches (woo_cache, eco_cache,
# scrape_status), so fewer workers = proportionally less RAM.
workers = int(os.environ.get("WEB_CONCURRENCY", 1))
threads = 2
timeout = 120

# Share application code across workers (saves ~30-50 MB per extra worker)
preload_app = True

# Cap worker memory: restart if a worker exceeds 450 MB (leaves headroom)
max_requests = 1000          # recycle workers every 1000 requests
max_requests_jitter = 50     # stagger restarts
