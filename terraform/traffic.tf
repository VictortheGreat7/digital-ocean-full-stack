resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"

  namespace        = "cert-manager"
  create_namespace = true

  atomic          = true
  cleanup_on_fail = true

  values = [file("${path.root}/helm/cert-manager/values.yaml")]

  timeout = 600

  depends_on = [digitalocean_kubernetes_cluster.kronos]
}

resource "helm_release" "cert_manager_prod_issuer" {
  chart      = "cert-manager-issuers"
  name       = "cert-manager-prod-issuer"
  repository = "https://charts.adfinis.com"
  namespace  = helm_release.cert_manager.namespace

  atomic          = true
  cleanup_on_fail = true

  values = [file("${path.root}/helm/cert-manager/prod-issuer-values.yaml")]

  depends_on = [
    helm_release.cert_manager,
    kubernetes_secret_v1.cloudflare_api
  ]
}

resource "helm_release" "cert_manager_stag_issuer" {
  chart      = "cert-manager-issuers"
  name       = "cert-manager-stag-issuer"
  repository = "https://charts.adfinis.com"
  namespace  = "cert-manager"

  atomic          = true
  cleanup_on_fail = true

  values = [file("${path.root}/helm/cert-manager/staging-issuer-values.yaml")]

  depends_on = [
    helm_release.cert_manager,
    kubernetes_secret_v1.cloudflare_api
  ]
}

resource "helm_release" "gateway_argocd" {
  name             = "gateway-argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-apps"
  namespace        = "knative-cd"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [file("${path.root}/helm/argocd/argocd-apps/gateway-values.yaml")]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.argo_cd,
    helm_release.cert_manager_prod_issuer,
    helm_release.cert_manager_stag_issuer
  ]
}
