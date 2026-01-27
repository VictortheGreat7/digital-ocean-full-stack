terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = ">= 2.72.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 3.0.1"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.1.1"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = ">= 2.1.3"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = ">= 5.15.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

provider "kubernetes" {
  host  = digitalocean_kubernetes_cluster.kronos.endpoint
  token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
  client_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
  )
  client_key = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
  )
  cluster_ca_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
  )
}

provider "helm" {
  kubernetes = {
    host  = digitalocean_kubernetes_cluster.kronos.endpoint
    token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
    client_certificate = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
    )
    client_key = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
    )
    cluster_ca_certificate = base64decode(
      digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
    )
  }
}

provider "kubectl" {
  host  = digitalocean_kubernetes_cluster.kronos.endpoint
  token = digitalocean_kubernetes_cluster.kronos.kube_config[0].token
  client_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_certificate
  )
  client_key = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].client_key
  )
  cluster_ca_certificate = base64decode(
    digitalocean_kubernetes_cluster.kronos.kube_config[0].cluster_ca_certificate
  )
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
