# Gunicorn configuration for Azure App Service
# This file enables proper request/error logging for diagnostics

import os
import sys

# Bind to the port Azure provides
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker configuration
workers = 1  # Start with 1 worker for easier debugging
worker_class = "sync"
threads = 2
timeout = 120  # Increased timeout for heavy data loading
graceful_timeout = 30
keepalive = 5

# Logging configuration - send everything to stdout for Azure
accesslog = "-"  # stdout
errorlog = "-"   # stdout
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Capture all output
capture_output = True
enable_stdio_inheritance = True

# Preloading helps with memory but we're avoiding it due to heavy import-time loads
preload_app = False  # Set to False to avoid blocking during module import

# Process naming
proc_name = "credit_boost_portal"

# Hooks for debugging
def on_starting(server):
    print("=" * 60, file=sys.stdout, flush=True)
    print("Gunicorn is starting...", file=sys.stdout, flush=True)
    print(f"Workers: {workers}", file=sys.stdout, flush=True)
    print(f"Timeout: {timeout}s", file=sys.stdout, flush=True)
    print("=" * 60, file=sys.stdout, flush=True)

def when_ready(server):
    print("=" * 60, file=sys.stdout, flush=True)
    print("Gunicorn is ready to accept connections!", file=sys.stdout, flush=True)
    print("=" * 60, file=sys.stdout, flush=True)

def worker_ready(worker):
    print(f"Worker {worker.pid} is ready", file=sys.stdout, flush=True)
