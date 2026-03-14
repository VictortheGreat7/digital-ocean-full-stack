bind = "0.0.0.0:5000"

workers = 4
worker_class = "gevent"
worker_connections = 250

backlog = 2048
keepalive = 5
timeout = 30
graceful_timeout = 30

control_socket_disable = True