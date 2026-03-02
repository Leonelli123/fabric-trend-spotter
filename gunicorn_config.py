"""Gunicorn configuration for production deployment.

Tuned for Render (512 MB RAM):
- 1 worker to keep all in-memory caches in a single process
- 2 threads for concurrent request handling within the single worker
- preload_app DISABLED so the scheduler starts inside the worker
  (with preload=True the scheduler runs in the master process, but
  data written there is invisible to the forked worker — a silent bug)
"""

import os

bind = "0.0.0.0:10000"

# 1 worker = one process handles everything (scheduler + HTTP).
# The gunicorn master arbiter is lightweight (~15 MB overhead).
workers = int(os.environ.get("WEB_CONCURRENCY", 1))
threads = 2
timeout = 120

# Do NOT preload: we need the scheduler to start inside the worker
# process so that scheduled refresh data (woo_cache, eco_cache) is
# visible to request handlers.  With preload=True, _start_scheduler()
# ran in the master process, and its writes were trapped there.
preload_app = False

# Recycle the worker periodically to reclaim fragmented memory
max_requests = 1000
max_requests_jitter = 50
