# This file is used to configure the backend for the terraform state file.
terraform {
  backend "azurerm" {
    resource_group_name  = "tfbackend-rg"
    storage_account_name = "kronos349"
    container_name       = "tfstate"
    key                  = "test.terraform.tfstate"
  }
}