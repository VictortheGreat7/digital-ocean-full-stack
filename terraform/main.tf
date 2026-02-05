resource "random_pet" "kronos" {}

module "doks" {
  source = "./modules/doks"

  random_pet         = random_pet.kronos.id
  region             = var.region
  kubernetes_version = data.digitalocean_kubernetes_versions.kronos.latest_version
  vpc_uuid           = digitalocean_vpc.kronos.id
  node_pool_name     = "kronos-pool"
  node_pool_size     = "s-4vcpu-8gb"
  node_pool_min_nodes = 1
  node_pool_max_nodes = 3
  tag_name           = digitalocean_tag.kronos.name
}

resource "digitalocean_project" "kronos" {
  name        = "kronos"
  description = "Kronos World Clock Project"
  purpose     = "Class project / Educational purposes"
  environment = "Development"
  resources = [module.doks.urn]

  depends_on = [module.doks]
}

resource "kubernetes_namespace_v1" "kronos" {
  metadata {
    name = "kronos"
  }

  depends_on = [module.doks]
}
