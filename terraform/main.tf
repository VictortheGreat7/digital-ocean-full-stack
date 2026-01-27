# This file contains the main Terraform configuration for creating an Azure Kubernetes Service (AKS) cluster for the Time API application.

resource "random_pet" "kronos" {}

resource "azurerm_resource_group" "jump_rg" {
  name     = "rg-${random_pet.kronos.id}-jump"
  location = var.azure_region
}

resource "azurerm_linux_virtual_machine" "jump_vm" {
  name                = "jump-${azurerm_resource_group.jump_rg.name}-vm"
  resource_group_name = azurerm_resource_group.jump_rg.name
  location            = azurerm_resource_group.jump_rg.location
  size                = "Standard_B1s"
  admin_username      = "kronosuser"
  network_interface_ids = [
    azurerm_network_interface.jump_nic.id,
  ]

  admin_ssh_key {
    username   = "kronosuser"
    public_key = file("${path.module}/ssh_keys/id_rsa.pub")
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    name                 = "jump-os-disk"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "ubuntu-pro"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tpl", {
    github_runner_token = var.github_runner_token
    do_api_token        = var.do_token
  }))

  lifecycle {
    ignore_changes = [
      custom_data
    ]
  }
}

output "ssh_command" {
  value = "ssh -i ssh_keys/id_rsa kronosuser@${azurerm_linux_virtual_machine.jump_vm.public_ip_address}"
}
