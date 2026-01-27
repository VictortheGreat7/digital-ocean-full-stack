resource "azurerm_virtual_network" "jump_vnet" {
  name                = "vnet-${azurerm_resource_group.jump_rg.name}"
  address_space       = ["10.240.0.0/16"]
  location            = azurerm_resource_group.jump_rg.location
  resource_group_name = azurerm_resource_group.jump_rg.name
}

resource "azurerm_subnet" "jump_subnet" {
  name                 = "jump-${azurerm_resource_group.jump_rg.name}-subnet"
  resource_group_name  = azurerm_resource_group.jump_rg.name
  virtual_network_name = azurerm_virtual_network.jump_vnet.name
  address_prefixes     = ["10.240.0.0/24"]
}

resource "azurerm_public_ip" "jump_public_ip" {
  name                = "jump-${azurerm_resource_group.jump_rg.name}-publicip"
  location            = azurerm_resource_group.jump_rg.location
  resource_group_name = azurerm_resource_group.jump_rg.name
  allocation_method   = "Dynamic"
  sku                 = "Basic"
}

resource "azurerm_network_interface" "jump_nic" {
  name                = "jump-${azurerm_resource_group.jump_rg.name}-nic"
  location            = azurerm_resource_group.jump_rg.location
  resource_group_name = azurerm_resource_group.jump_rg.name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.jump_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.jump_public_ip.id
  }
}

resource "azurerm_network_security_group" "jump_nsg" {
  name                = "jump-${azurerm_resource_group.jump_rg.name}-nsg"
  location            = azurerm_resource_group.jump_rg.location
  resource_group_name = azurerm_resource_group.jump_rg.name

  security_rule {
    name                       = "SSH"
    priority                   = 101
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "allow-vnet-inbound"
    priority                   = 102
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "deny-all-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface_security_group_association" "nsg_assoc" {
  network_interface_id      = azurerm_network_interface.jump_nic.id
  network_security_group_id = azurerm_network_security_group.jump_nsg.id
}

resource "digitalocean_vpc" "kronos" {
  name     = "${random_pet.kronos.id}-vnet"
  region   = var.region
  ip_range = "10.240.0.0/16"
}

resource "digitalocean_vpc_nat_gateway" "kronos" {
  name   = "${random_pet.kronos.id}-natgw"
  type   = "PUBLIC"
  region = var.region
  size   = "1"
  vpcs {
    vpc_uuid        = digitalocean_vpc.kronos.id
    default_gateway = true
  }
  tcp_timeout_seconds  = 30
  udp_timeout_seconds  = 30
  icmp_timeout_seconds = 30
}

resource "digitalocean_tag" "kronos" {
  name = "kronos"
}

resource "digitalocean_firewall" "kronos" {
  name = "${random_pet.kronos.id}-firewall"

  tags = [digitalocean_tag.kronos.name]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0"]
  }
}
