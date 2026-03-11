bind = "0.0.0.0:5000"

workers = 4
worker_class = "gevent"
worker_connections = 300

backlog = 2048
accesslog = None
keepalive = 5
timeout = 60
graceful_timeout = 30

control_socket_disable = True