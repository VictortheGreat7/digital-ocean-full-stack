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
  host  = module.doks.api_server_endpoint
  token = module.doks.kubeconfig.token
  client_certificate = base64decode(
    module.doks.kubeconfig.client_certificate
  )
  client_key = base64decode(
    module.doks.kubeconfig.client_key
  )
  cluster_ca_certificate = base64decode(
    module.doks.kubeconfig.cluster_ca_certificate
  )
}

provider "helm" {
  kubernetes = {
    host  = module.doks.api_server_endpoint
    token = module.doks.kubeconfig.token
    client_certificate = base64decode(
      module.doks.kubeconfig.client_certificate
    )
    client_key = base64decode(
      module.doks.kubeconfig.client_key
    )
    cluster_ca_certificate = base64decode(
      module.doks.kubeconfig.cluster_ca_certificate
    )
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
