import os

# Gunicorn configuration for Render (512MB RAM limit)
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 2  # Fixed low count to stay within 512MB memory limit
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"

# Worker recycling — restart workers after N requests to free leaked memory
max_requests = 500
max_requests_jitter = 50

# Preload app to share memory between workers via copy-on-write
preload_app = True
