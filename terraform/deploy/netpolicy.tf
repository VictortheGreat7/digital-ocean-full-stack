# # This file contains the Kubernetes Network Policies for the time-api namespace.

# resource "kubernetes_network_policy_v1" "default_deny" {
#   metadata {
#     name      = "default-deny-all"
#     namespace = "kronos"
#   }

#   spec {
#     pod_selector {
#       match_labels = {
#         app = "kronos-app"
#       }
#     }

#     policy_types = ["Ingress", "Egress"]
#    }

#   depends_on = [azurerm_kubernetes_cluster.kronos_cluster]
# }

# resource "kubernetes_network_policy_v1" "allow_dns" {
#   metadata {
#     name      = "allow-dns-access"
#     namespace = "kronos"
#   }

#   spec {
#     pod_selector {
#       match_labels = {
#         app = "kronos-app"
#       }
#     }

#     policy_types = ["Ingress", "Egress"]

#     ingress {
#       ports {
#         protocol = "UDP"
#         port     = 53
#       }
#       ports {
#         protocol = "TCP"
#         port     = 53
#       }
#     }

#     egress {
#       ports {
#         protocol = "UDP"
#         port     = 53
#       }
#       ports {
#         protocol = "TCP"
#         port     = 53
#       }
#     }
#   }

#   depends_on = [kubernetes_network_policy_v1.default_deny]
# }

# resource "kubernetes_network_policy_v1" "allow_ingress" {
#   metadata {
#     name      = "allow-ingress-to-kronos-app"
#     namespace = "kronos"
#   }

#   spec {
#     pod_selector {
#       match_labels = {
#         app = "kronos-app"
#       }
#     }

#     policy_types = ["Ingress"]

#     # Defines the allowed incoming traffic
#     ingress {
#       from {
#         namespace_selector {
#           match_labels = {
#             "kubernetes.io/metadata.name" = "kube-system"
#           }
#         }
#         pod_selector {
#           match_labels = {
#             "app.kubernetes.io/name" = "ingress-nginx"
#           }
#         }
#       }

#       from {
#         namespace_selector {
#           match_labels = {
#             "kubernetes.io/metadata.name" = "kronos"
#           }
#         }
#         pod_selector {
#           match_labels = {
#             "job-name" = "kronos-backend-test"
#             "job-name" = "kronos-frontend-test"
#           }
#         }
#       }

#       # Allow traffic on specific ports
#       ports {
#         protocol = "TCP"
#         port     = 5000
#       }
#       ports {
#         protocol = "TCP"
#         port     = 80
#       }
#     }
#   }

#   depends_on = [kubernetes_network_policy_v1.default_deny]
# }
