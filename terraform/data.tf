# This file contains the data sources that are used in the Terraform configuration.
data "digitalocean_kubernetes_versions" "kronos" {}

data "digitalocean_kubernetes_cluster" "kronos" {
  name = module.doks.name

  depends_on = [module.doks]
}

data "kubernetes_service_v1" "nginx_ingress" {
  metadata {
    name      = "ingress-nginx-controller"
    namespace = "kube-system"
  }

  depends_on = [module.nginx-controller]
}
