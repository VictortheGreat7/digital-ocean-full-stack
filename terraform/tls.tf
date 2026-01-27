resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"

  create_namespace = true
  namespace        = "cert-manager"

  set = [
    {
      name  = "installCRDs"
      value = "true"
    },
    {
      name = "resources.requests.cpu"
      value = "100m"
    },
    {
      name = "resources.requests.memory"
      value = "256Mi"
    },
    {
      name = "resources.limits.cpu"
      value = "200m"
    },
    {
      name = "resources.limits.memory"
      value = "512Mi"
    }
  ]

  timeout = 600

  depends_on = [
    module.nginx-controller,
    kubernetes_job_v1.wait_for_ingress_webhook
  ]
}

resource "helm_release" "cert_manager_prod_issuer" {
  chart      = "cert-manager-issuers"
  name       = "cert-manager-prod-issuer"
  repository = "https://charts.adfinis.com"
  namespace  = helm_release.cert_manager.namespace

  values = [
    <<-EOT
clusterIssuers:
  - name: letsencrypt-prod
    spec:
      acme:
        email: "greatvictor.anjorin@gmail.com"
        server: "https://acme-v02.api.letsencrypt.org/directory"
        privateKeySecretRef:
          name: letsencrypt-prod
        solvers:
          - dns01:
              cloudflare:
                email: "greatvictor.anjorin@gmail.com"
                apiTokenSecretRef:
                  name: cloudflare-api
                  key: api-token               
EOT
  ]

  depends_on = [
    helm_release.cert_manager,
    kubernetes_secret_v1.cloudflare_api
  ]
}

# resource "helm_release" "cert_manager_stag_issuer" {
#   chart      = "cert-manager-issuers"
#   name       = "cert-manager-stag-issuer"
#   repository = "https://charts.adfinis.com"
#   namespace  = "cert-manager"

#   values = [
#     <<-EOT
# clusterIssuers:
#   - name: letsencrypt-staging
#     spec:
#       acme:
#         email: "greatvictor.anjorin@gmail.com"
#         server: "https://acme-staging-v02.api.letsencrypt.org/directory"
#         privateKeySecretRef:
#           name: letsencrypt-staging
#         solvers:
#           - dns01:
#               cloudflare:
#                 email: "greatvictor.anjorin@gmail.com"
#                 apitokensecret:
#                   name: cloudflare-api
#                   key: api-token               
# EOT
#   ]

#   depends_on = [helm_release.cert_manager, kubernetes_secret_v1.cloudflare_api]
# }