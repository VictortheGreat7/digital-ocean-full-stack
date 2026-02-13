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
            backendRefs = [
              {
                name = "argocd-server"
                port = 80
              }
            ]
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
    configs = {
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

resource "helm_release" "argocd_apps" {
  name             = "argocd-apps"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argocd-apps"
  namespace        = "knative-cd"
  create_namespace = false
  atomic           = true
  cleanup_on_fail  = true

  values = [yamlencode({
    applications = {
      guestbook = {
        namespace = "kronos"
        project   = "guestbook"
        source = {
          repoURL = "https://github.com/VictortheGreat7/kronos-app.git"
          targetRevision = "main"
          # path = "kronos-app"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "kronos"
        }
        syncPolicy = {
          automated = {
            prune    = true
            selfHeal = true
          }
          syncOptions = [
            "CreateNamespace=true"
          ]
        }
      }
    }
  })]

  wait    = true
  timeout = 600

  depends_on = [
    digitalocean_kubernetes_cluster.kronos,
    helm_release.argo_cd
  ]
}