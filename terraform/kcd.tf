resource "helm_release" "argo_cd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  namespace        = "knative-cd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.module}/../helm/argocd/values.yaml", {
      kronos_domain = "${var.subdomains[0]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}
