# This file contains the data sources that are used in the Terraform configuration.
data "digitalocean_kubernetes_versions" "kronos" {}

data "digitalocean_kubernetes_cluster" "kronos" {
  name = module.doks.name

  depends_on = [module.doks]
}

data "kubernetes_service_v1" "cilium_gateway" {
  metadata {
    name      = "cilium-gateway-kronos"
    namespace = "cert-manager"
  }

  depends_on = [kubernetes_manifest.cilium_gateway]
}
