# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
threads = 2
control_socket_disable = True