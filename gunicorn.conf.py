# gunicorn.conf.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "gevent"  # For async streaming
