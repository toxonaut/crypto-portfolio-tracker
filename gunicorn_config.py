import multiprocessing

# Gunicorn configuration
bind = "0.0.0.0:8080"
workers = 1  # Start with a single worker to minimize memory usage
worker_class = "sync"
timeout = 120  # Increase timeout to 120 seconds
max_requests = 1000
max_requests_jitter = 50
preload_app = True  # Preload the application code
