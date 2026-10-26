# gunicorn.conf.py
workers = 1
worker_class = 'sync'
timeout = 60
max_requests = 50
max_requests_jitter = 5
accesslog = '-'
errorlog = '-'
loglevel = 'info'