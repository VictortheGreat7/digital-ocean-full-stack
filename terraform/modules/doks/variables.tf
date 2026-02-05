variable random_pet {
  type        = string
  description = "Random pet name for unique resource naming"
}

variable region {
  type        = string
  description = "The region where the resources will be created"
}

variable kubernetes_version {
  type        = string
  description = "The version of Kubernetes to use for the cluster"
}

variable vpc_uuid {
  type        = string
  description = "The UUID of the VPC to use for the cluster"
}

variable node_pool_name {
  type        = string
  default     = "worker-pool"
  description = "The name of the node pool"
}

variable node_pool_size {
  type        = string
  default     = "s-4vcpu-8gb"
  description = "The size of the nodes in the node pool"
}

variable node_pool_min_nodes {
  type        = number
  default     = 1
  description = "The minimum number of nodes in the node pool"
}

variable node_pool_max_nodes {
  type        = number
  default     = 3
  description = "The maximum number of nodes in the node pool"
}

variable tag_name {
  type        = string
  description = "The name of the tag to apply to resources"
}
