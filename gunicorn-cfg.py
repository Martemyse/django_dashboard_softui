# gunicorn-cfg.py

bind = "0.0.0.0:8010"  # Make Gunicorn listen on all network interfaces
workers = 1  # Or use `multiprocessing.cpu_count() * 2 + 1` for dynamic scaling
accesslog = '-'  # Keep standard logging
loglevel = 'info'  # Lower logging level for production
capture_output = True
enable_stdio_inheritance = True
forwarded_allow_ips = '*'  # Trust all proxies
