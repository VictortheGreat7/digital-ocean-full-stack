bind = "0.0.0.0:5000"

workers = 4
worker_class = "gthread"
threads = 50 

backlog = 2048
keepalive = 2
timeout = 10
graceful_timeout = 30

control_socket_disable = True