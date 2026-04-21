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
      argo_hostname = "${var.subdomains[0]}.${var.domain}"
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
      cluster_name          = digitalocean_kubernetes_cluster.kronos.name,
      prometheus_hostname   = "${var.subdomains[1]}.${var.domain}",
      alertmanager_hostname = "${var.subdomains[2]}.${var.domain}",
      grafana_hostname      = "${var.subdomains[3]}.${var.domain}",
      kronos_hostname       = "${var.subdomains[4]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.argo_cd,
    helm_release.external_dns,
    kubernetes_secret_v1.postgres_pass,
    kubernetes_secret_v1.pgbouncer_auth,
    kubernetes_secret_v1.datadog_secret
  ]
}
