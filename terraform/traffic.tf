resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"

  namespace        = "cert-manager"
  create_namespace = true

  atomic          = true
  cleanup_on_fail = true

  values = [file("${path.root}/terraform-helm/cert-manager/values.yaml")]

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

  values = [
    templatefile("${path.root}/terraform-helm/cert-manager/prod-issuer-values.yaml", {
      issuer_email = var.email
    })
  ]

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

  values = [
    templatefile("${path.root}/terraform-helm/cert-manager/staging-issuer-values.yaml", {
      issuer_email = var.email
    })
  ]

  depends_on = [
    helm_release.cert_manager,
    kubernetes_secret_v1.cloudflare_api
  ]
}

resource "helm_release" "gateway" {
  name             = "main"
  repository       = "https://subshell.github.io/helm-charts"
  chart            = "gateway"
  namespace        = "kube-system"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/traffic/gateway/values.yaml", {
      hostname = "${var.subdomains[0]}.${var.domain}"
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.cert_manager_prod_issuer,
    helm_release.cert_manager_stag_issuer
  ]
}

resource "helm_release" "external_dns" {
  name       = "external-dns"
  repository = "https://kubernetes-sigs.github.io/external-dns/"
  chart      = "external-dns"
  namespace  = "kube-system"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [
    templatefile("${path.root}/terraform-helm/traffic/external-dns/values.yaml", {
      subdomain = var.subdomains[0]
    })
  ]

  wait    = true
  timeout = 600

  depends_on = [
    helm_release.gateway,
    kubernetes_secret_v1.cloudflare_api
  ]
}
