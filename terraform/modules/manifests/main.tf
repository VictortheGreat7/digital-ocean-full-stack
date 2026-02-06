terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 3.0.1"
    }
  }
}

provider "kubernetes" {
  host                   = var.doks_host
  token                  = var.doks_token
  client_certificate     = var.doks_client_certificate
  client_key             = var.doks_client_key
  cluster_ca_certificate = var.doks_cluster_ca_certificate
}

resource "kubernetes_manifest" "cilium_gateway" {
  manifest = var.cilium_gateway_manifest
}

resource "kubernetes_manifest" "kronos_http_route" {
  manifest = var.kronos_http_route_manifest

  depends_on = [
    kubernetes_manifest.cilium_gateway
  ]
}

resource "kubernetes_manifest" "kronos_https_route" {
  manifest = var.kronos_https_route_manifest

  depends_on = [
    kubernetes_manifest.cilium_gateway,
    kubernetes_manifest.kronos_http_route
  ]
}

resource "kubernetes_manifest" "k6_test" {
  manifest = var.k6_test_manifest
}
