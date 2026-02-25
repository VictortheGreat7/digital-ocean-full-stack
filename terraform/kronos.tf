# resource "helm_release" "kronos_argocd" {
#   name             = "kronos-argocd"
#   repository       = "https://argoproj.github.io/argo-helm"
#   chart            = "argocd-apps"
#   namespace        = "knative-cd"
#   create_namespace = false
#   atomic           = true
#   cleanup_on_fail  = true

#   values = [file("${path.root}/terraform-helm/argocd/argocd-apps/app-values.yaml")]

#   wait    = true
#   timeout = 600

#   depends_on = [
#     helm_release.monitoring_argocd,
#     kubernetes_secret_v1.postgres_pass
#   ]
# }
