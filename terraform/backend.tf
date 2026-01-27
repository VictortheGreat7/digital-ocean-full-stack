# This file is used to configure the backend for the terraform state file.
terraform {
  cloud {
    organization = "VictortheGreat7-TF"

    workspaces {
      name = "digital-ocean-full-stack"
    }
  }
}