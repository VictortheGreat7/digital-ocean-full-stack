resource "helm_release" "argo_cd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  namespace        = "knative-cd"
  create_namespace = true
  atomic           = true
  cleanup_on_fail  = true

  values = [yamlencode({
    server = {
      httproute = {
        enabled = true
        parentRefs = [{
          name        = "kronos"
          namespace   = "kube-system"
          sectionName = "https"
        }]
        hostnames = ["${var.subdomains[0]}.${var.domain}"]
        rules = [
          {
            matches = [
              {
                path = {
                  type  = "PathPrefix"
                  value = "/kcd/argo"
                }
              }
            ]
          }
        ]
      }
    }
    config = {
      params = {
        "server.basehref" = "/kcd/argo"
        "server.rootpath" = "/kcd/argo"
        "server.insecure" = "true"
      }
    }
  })]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos
  ]
}