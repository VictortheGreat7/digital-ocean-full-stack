output "doks_cluster_name" {
  value = digitalocean_kubernetes_cluster.kronos.name
}
output "doks_cluster_id" {
  value = digitalocean_kubernetes_cluster.kronos.id
}

output "ingress_ip" {
  value = data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip
}
