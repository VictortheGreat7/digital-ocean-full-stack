# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
threads = 2
no_control_socket = True