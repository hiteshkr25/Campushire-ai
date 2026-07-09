import os

bind = "0.0.0.0:8000"

# Production-safe worker configuration to prevent memory limit exhaustion.
# For low-memory environments (such as 512 MB instances like Replit or basic containers), 
# we restrict the server to a single worker (1) to prevent Out-Of-Memory (OOM) crashes.
# For larger/scalable production environments, this can be configured via GUNICORN_WORKERS.
workers = int(os.environ.get("GUNICORN_WORKERS", 1))

worker_class = "sync"
timeout = 120
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
