# This file contains the data sources that are used in the Terraform configuration.
data "digitalocean_kubernetes_cluster" "kronos" {
  name = digitalocean_kubernetes_cluster.kronos.name
}

data "kubernetes_service_v1" "nginx_ingress" {
  metadata {
    name      = "ingress-nginx-controller"
    namespace = "kube-system"
  }
}
