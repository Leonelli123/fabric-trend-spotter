"""Gunicorn configuration for production deployment."""

bind = "0.0.0.0:10000"
workers = 2
threads = 2
timeout = 120
