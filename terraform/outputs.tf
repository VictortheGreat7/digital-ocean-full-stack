output "doks_connect" {
  value = "doctl kubernetes cluster kubeconfig save ${module.doks.name}"
}

output doks_cluster_id {
  value       = module.doks.cluster_id
  sensitive   = true
}

# output "ingress_ip" {
#   value = data.kubernetes_service_v1.cilium_gateway.status.0.load_balancer.0.ingress.0.ip
# }
