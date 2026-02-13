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
      gateway = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL = "https://github.com/VictortheGreat7/monitoring.git"
          targetRevision = "main"
          path = "gateway"
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "kube-system"
        }
        syncPolicy = {
          automated = {
            prune    = true
            selfHeal = true
          }
        }
      },
      kronos = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/kronos-app.git"
          targetRevision = "main"
          path           = "."
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
      },
      kube-prom-stack = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/monitoring.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://prometheus-community.github.io/helm-charts"
            chart          = "kube-prometheus-stack"
            targetRevision = "81.6.7"
            helm = {
              valueFiles = ["$values/helm/values.yaml"]
            }
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "monitoring"
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
      },
      # datadog = {
      #   namespace = "knative-cd"
      #   project   = "default"
      #   source = {
      #     repoURL        = "https://github.com/VictortheGreat7/monitoring.git"
      #     targetRevision = "main"
      #     path           = "helm"
      #     helm = {
      #       chart      = "datadog"
      #       repoURL    = "https://helm.datadoghq.com"
      #       valueFiles = ["datadog-values.yaml"]
      #     }
      #     destination = {
      #       server    = "https://kubernetes.default.svc"
      #       namespace = "datadog"
      #     }
      #     syncPolicy = {
      #       automated = {
      #         prune    = true
      #         selfHeal = true
      #       }
      #       syncOptions = [
      #         "CreateNamespace=true"
      #       ]
      #     }
      #   }
      # },
      chaos-operator = {
        namespace = "knative-cd"
        project   = "default"
        sources = [
          {
            repoURL        = "https://github.com/VictortheGreat7/chaos-testing.git"
            targetRevision = "main"
            ref            = "values"
          },
          {
            repoURL        = "https://grafana.github.io/helm-charts"
            chart          = "k6-operator"
            targetRevision = "4.2.0"
            valueFiles     = ["$values/helm/values.yaml"]
          }
        ]
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "chaos"
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
      },
      chaos-test = {
        namespace = "knative-cd"
        project   = "default"
        source = {
          repoURL        = "https://github.com/VictortheGreat7/chaos-testing.git"
          targetRevision = "main"
          path           = "."
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "chaos"
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