output "doks_connect" {
  value = "doctl kubernetes cluster kubeconfig save ${module.doks.name}"
}

output "ingress_ip" {
  value = data.kubernetes_service_v1.nginx_ingress.status.0.load_balancer.0.ingress.0.ip
}
