# This file contains the data sources that are used in the Terraform configuration.
data "digitalocean_kubernetes_versions" "kronos" {}

data "digitalocean_kubernetes_cluster" "kronos" {
  name = module.doks.name

  depends_on = [module.doks]
}

data "kubernetes_service_v1" "cilium_gateway" {
  metadata {
    name      = "cilium-gateway-kronos"
    namespace = "kube-system"
  }

  depends_on = [helm_release.kube_prometheus_stack]
}
