resource "random_pet" "kronos" {}

resource "digitalocean_kubernetes_cluster" "kronos" {
  name     = "${random_pet.kronos.id}-cluster"
  region   = var.region
  version  = data.digitalocean_kubernetes_versions.kronos.latest_version
  vpc_uuid = digitalocean_vpc.kronos.id

  node_pool {
    name       = "kronos-pool"
    size       = "s-4vcpu-8gb"
    auto_scale = true
    min_nodes  = 1
    max_nodes  = 3
    tags       = [digitalocean_tag.kronos.name]
  }

  auto_upgrade                     = true
  surge_upgrade                    = true
  destroy_all_associated_resources = true

  tags = [digitalocean_tag.kronos.name]
}

resource "helm_release" "descheduler" {
  name       = "descheduler"
  repository = "https://kubernetes-sigs.github.io/descheduler/"
  chart      = "descheduler"

  namespace        = "kube-system"
  create_namespace = false

  atomic          = true
  cleanup_on_fail = true

  values = [file("${path.root}/terraform-helm/descheduler/values.yaml")]

  timeout = 600

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "kubernetes_service_account_v1" "headlamp-admin" {
  metadata {
    name = "headlamp-admin"
    namespace = "kube-system"
  }

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "kubernetes_cluster_role_binding_v1" "headlamp-admin" {
  metadata {
    name = "headlamp-admin"
  }
  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }
  subject {
    kind      = "ServiceAccount"
    name      = "headlamp-admin"
    namespace = "kube-system"
  }

  depends_on = [kubernetes_service_account_v1.headlamp-admin]
}

resource "helm_release" "headlamp" {
  name             = "headlamp"
  repository       = "https://kubernetes-sigs.github.io/headlamp/"
  chart            = "headlamp"
  namespace        = "kube-system"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/headlamp/values.yaml", {
      headlamp_hostname       = "${var.subdomains[5]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [kubernetes_cluster_role_binding_v1.headlamp-admin]
}

resource "kubernetes_token_request_v1" "headlamp-admin" {
  metadata {
    name = kubernetes_service_account_v1.headlamp-admin.metadata.0.name
  }
  spec {}

  depends_on = [helm_release.headlamp]
}

# resource "digitalocean_project" "kronos" {
#   name        = "kronos"
#   description = "Kronos World Clock Project"
#   purpose     = "Class project / Educational purposes"
#   environment = "Development"
#   resources   = [digitalocean_kubernetes_cluster.kronos.urn]

#   depends_on = [digitalocean_kubernetes_cluster.kronos]
# }
