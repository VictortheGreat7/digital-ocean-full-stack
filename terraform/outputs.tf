output "doks_connect" {
  value = "doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.kronos.name}"
}

output "doks_cluster_name" {
  value     = digitalocean_kubernetes_cluster.kronos.name
  sensitive = true
}

output "doks_cluster_id" {
  value     = digitalocean_kubernetes_cluster.kronos.id
  sensitive = true
}

# output "ingress_ip" {
#   value = data.kubernetes_service_v1.cilium_gateway.status.0.load_balancer.0.ingress.0.ip
# }
