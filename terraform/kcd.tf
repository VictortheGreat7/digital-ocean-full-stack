resource "helm_release" "argo_cd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  namespace        = "knative-cd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/argocd/values.yaml", {
      kronos_domain = "${var.subdomains[0]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}

resource "helm_release" "parent_app" {
  name             = "parent"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-apps"
  namespace        = "knative-cd"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/argocd/app-of-apps.yaml", {
      cluster_name = digitalocean_kubernetes_cluster.kronos.name,
      hostname     = "${var.subdomains[0]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.gateway,
    helm_release.kronos_argocd,
    kubernetes_secret_v1.postgres_pass,
    kubernetes_secret_v1.datadog_secret
  ]
}
