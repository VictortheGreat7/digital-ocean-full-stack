# This file contains the provider configurations for the Microsoft Azure Cloud Infrastructure for the Time API application.

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
