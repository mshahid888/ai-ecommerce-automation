# gunicorn.conf.py — ALTERNATIVE process manager for the demo backend.
#
# This is provided as an alternative to the systemd+uvicorn-workers setup
# (see ecommerce-demo.service). Either one serves app.main:app; do not run
# both at the same time.
#
# Usage: /srv/ai-ecommerce-automation/backend/.venv/bin/gunicorn \
#            -c deploy/gunicorn.conf.py app.main:app
#
# NOTE: gunicorn is NOT in requirements.txt. If you prefer this route, add
# `gunicorn` (and uvicorn[standard] workers) to requirements on the server.

bind = "127.0.0.1:8000"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 100
timeout = 30               # must exceed LLM_TIMEOUT_SECONDS (default 15)
graceful_timeout = 10
keepalive = 5
# Trust X-Forwarded-* from nginx so per-IP rate limiting sees real clients.
# Safe only because we bind 127.0.0.1 behind our own reverse proxy.
forwarded_allow_ips = "127.0.0.1"
loglevel = "info"
accesslog = "-"
errorlog = "-"
