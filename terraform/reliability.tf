resource "helm_release" "monitoring_argocd" {
  name             = "monitoring-argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-apps"
  namespace        = "knative-cd"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/argocd/argocd-apps/monitoring-values.yaml", {
      cluster_name = digitalocean_kubernetes_cluster.kronos.name
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.gateway,
    kubernetes_secret_v1.datadog_secret
  ]
}

# resource "helm_release" "chaos_argocd" {
#   name             = "chaos-argocd"
#   repository       = "https://argoproj.github.io/argo-helm"
#   chart            = "argocd-apps"
#   namespace        = "knative-cd"
#   create_namespace = false
#   atomic           = true
#   cleanup_on_fail  = true

#   values = [file("${path.root}/terraform-helm/argocd/argocd-apps/chaos-values.yaml")]

#   wait    = true
#   timeout = 600

#   depends_on = [
#     helm_release.kronos_argocd,
#     helm_release.monitoring_argocd
#   ]
# }
