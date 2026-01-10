# Time API Infrastructure Project

A cloud-native infrastructure project that deploys a simple World Clock Dashboard App to Azure Kubernetes Service (AKS)

The branch is for a more secure setup that restricts access to the AKS API server to a private VNet and uses a self-hosted GitHub Actions runner (within the same VNet) when there is a need to access it during CI/CD, eliminating the need to expose the cluster publicly.

This project is designed to demonstrate cloud engineering skills, including Infrastructure as Code (IaC), containerization, orchestration, monitoring and CI/CD automation.

## 🏗️ Architecture Overview

This project demonstrates a deployment of a simple API written in Python that returns the current UTC time of various locations around the world and a Vite frontend that displays them. It includes the use of the following:

- **API**: Simple Flask API that returns current UTC time for various locations
- **Frontend**: Vite application that displays the time data from the API
- **Containerisation**: Docker for test-running and building the application container
- **Orchestration**: Kubernetes for container orchestration
- **Cloud Infrastructure**: Azure Kubernetes Service (AKS) for hosting the application
- **Networking**: Azure Load Balancer and NGINX Ingress Controller for traffic management
- **CI/CD**: GitHub Actions for automated deployment
- **Monitoring**: Microsoft Log Analytics and kube-prometheus-stack (Prometheus and Grafana) for monitoring and observability
- **Security**: GitHub Secrets, Network Security Group, Microsoft Azure Role Based Access Control, Network policies and isolating API Server access to a private VNet
- **Infrastructure as Code**: The use of Terraform and Bash scripts running Microsoft Azure CLI and GitHub CLI commands for scripting/automation purposes
- **SSL/TLS**:

## 📋 Prerequisites

Before getting started, ensure you have installed and configured the following tools and services for your local machine and CI/CD environment:

### Required Tools

- [Microsoft Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- [GitHub CLI](https://cli.github.com/)
- [Terraform](https://www.terraform.io/downloads.html) >= 1.12.2
- [kubelogin](https://azure.github.io/kubelogin/install.html)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [Docker](https://docs.docker.com/get-docker/)

### Required Accounts & Services

- **Microsoft Azure Account** with a student or paid subscription and appropriate permissions (an Owner role is preferable)
- **Docker Hub Account** as a container registry
- **GitHub Repository** for version control and CI/CD automation

### Required Permissions

- Microsoft Azure subscription with `Owner` role is preferable
- Permission to create and manage Microsoft Azure AD groups and service principals

## 🚀 Quick Start

### 1. Fork and Clone the Repository

Fork this repository to your GitHub account (to fork other branches too, untick the copy only main branch option)

### 2. Clone the fork to your local machine or use Codespaces

```bash
git clone https://github.com/VictortheGreat7/self-hosted-full-stack.git YOUR-CHOSEN-REPO-NAME/
cd YOUR-CHOSEN-REPO-NAME
```

### 3. Set Up Microsoft Azure Service Principal

Create a service principal for GitHub Actions:

```bash
# Login to Microsoft Azure
az login --use-device-code

# Update the service_principal.sh script variables with your details before running it. You can find it here:
cd terraform/bash_scripts

# Run the service principal creation script
chmod +x service_principal.sh
./service_principal.sh
```

**Required Variables**:

- `SERVICE_PRINCIPAL_NAME`: Choose a unique name
- `SCOPE`: Your Microsoft Azure subscription ID
- `GITHUB_NAME`: Your GitHub username  
- `GITHUB_REPO`: Your repository name

A secrets.yaml file will be created in whatever repository you execute the script, with the details of the created service principal

### 4. Configure GitHub Secrets

Set up the required GitHub repository secrets. You can use the provided script:

```bash
chmod +x gh_secret.sh
# Edit the script with your secret values first
./gh_secret.sh
```

**Required Values/Secrets**:

- `AZURE_CREDENTIALS`: JSON object with Microsoft Azure service principal details
- `ARM_CLIENT_ID`: Microsoft Azure service principal client ID
- `ARM_CLIENT_SECRET`: Microsoft Azure service principal client secret
- `ARM_SUBSCRIPTION_ID`: Your Microsoft Azure subscription ID
- `ARM_TENANT_ID`: Your Microsoft Azure tenant ID
- `MY_USER_OBJECT_ID`: Your Microsoft Azure AD user object ID
- `RUNNER_TOKEN`: GitHub Actions runner token for the self-hosted runner. Find out how [`here`](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners). The cloud-init file for the runner vm already follows the instructions listed. All you need to do is copy the time-limited token with ./config.sh in the configure step. Just make sure you select Linux x64 architecture ![Visual of Token Location](./screenshots/runner_token.png)
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password/token

**Note**: For the needed Microsoft Azure account details, check secrets.yaml created by the [Service Principal creation](#2-set-up-microsoft-azure-service-principal) step.

### 5. Update Configuration

Edit the following files with your specific details:

#### `terraform/bash_scripts/pre-apply.sh`

```bash
# Update these variables
RESOURCE_GROUP_NAME="" # Change this
STORAGE_ACCOUNT_NAME="" # Choose a unique name
CONTAINER_NAME="tfstate"
REGION="eastus"
```

#### `terraform/backend.tf`

```hcl
terraform {
  backend "azurerm" {
    resource_group_name = "" # Update this
    storage_account_name = ""  # Update this
    container_name = "tfstate"
    key = "terraform.tfstate"
  }
}
```

#### `terraform/deploy/providers.tf`

```hcl
provider "azurerm" {
  features {}

  subscription_id = "YOUR-SUBSCRIPTION-ID"  # Update this
}
```

### 6. Deploy Infrastructure

Uncomment or add on-push trigger in .github/workflows/build.yaml and ensure other workflows will not trigger on push (except the app is up and you need to apply changes will integrate.yaml).

```yaml
# on:
#   push:
#     branches:
#       - main
```

Push your changes to trigger the GitHub Actions workflow:

```bash
git add .
git commit -m "[YOUR COMMIT MESSAGE]"
git push origin main
```

The workflow will:

1. Build and test the Docker image
2. Push the image to Docker Hub
3. Provision part of Microsoft Azure infrastructure needed including the self-hosted runner with Terraform using a GitHub hosted Actions runner
4. Provision the rest of the infrastructure using the self-hosted runner
5. Deploy the application to AKS

**Important**: You can only connect to the cluster rom your self-hosted runner. There is also an ssh command in the outputs printed after a successful `terraform apply` that you can use to connect to the self-hosted runner for any sort of troubleshooting or the other.

## 🏗️ Manual Deployment (Alternative)

If you prefer to deploy manually and you have updated the configuraton as specified above:

### Main Branch

#### 1. Create or confirm existing Terraform Backend

```bash
cd terraform/bash_scripts
chmod +x pre-apply.sh
./pre-apply.sh
```

#### 2. Provision Infrastructure and Self-Hosted Runner

```bash
cd ../
terraform init
terraform apply
```

#### 3. Deploy Application with Self-Hosted Runner

```bash
# Move microservice configs
cd deploy/
mv * ../
cd ../

# Create SSH keys for the self-hosted runner
ssh-keygen -t rsa -b 4096 -C "github-selfhosted-runner" -f ssh_keys/id_rsa

# Apply microservice deployment
terraform init
terraform apply
```

#### 4. Test API endpoint

In the outputs printed after a successful `terraform apply`, you will see the ingress IP of the deployed API. You can test it using:

```bash
curl http://<your-ingress-ip>
```

or with just `http://<your-ingress-ip>` in your browser.

**Important**: You can only [connect to the cluster](#useful-commands) in this scenario from you self-hosted runner. There is also an ssh command in the outputs printed after a successful `terraform apply` that you can use to connect to the self-hosted runner for any sort of troubleshooting.

## 🔧 Local Application/Image Building and/or Testing

### Running the Application Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python app.py

# Frontend (in a new terminal)
cd frontend
npm install
npm run dev
```

Access the application
Frontend: `http://localhost:5173` (or the port shown in terminal)
API: `http://localhost:5000/world-clocks`

### Building and Testing Docker Image

```bash
# Build the backend image
cd backend
docker build -t kronos:backend .
docker run -d -p 5000:5000 --name kronos-backend-local kronos:backend

# Build the frontend image
cd frontend
docker build -t kronos:frontend .
docker run -d -p 5173:80 --name kronos-frontend-local kronos:frontend

# Test the endpoint
curl http://localhost:5000/world-clocks
# and access http://localhost:80 in your browser to check frontend

# Clean up
docker stop kronos-frontend-local
docker stop kronos-backend-local
docker rm kronos-frontend-local
docker rm kronos-backend-local
```

## 📊 Monitoring and Observability

The project includes comprehensive monitoring:

- **Grafana Dashboard**: Visual monitoring interface
- **Prometheus**: Metrics scraping
- **Microsoft Azure Log Analytics**: Centralized logging

Access your Grafana dashboard through the terraform ingress outputs after deployment.

## 🔒 Security Features

- **Network Policies**: Restrict namespace communication to an as-needed basis
- **GitHub Secrets**: Secure storage of sensitive tokens
- **Service Principals**: Secure access for GitHub Actions
- **Microsoft Azure RBAC**: Role-based access control
- **Network Security Groups**: Microsoft Azure Network-level security
- **Private Subnets**: Isolated network segments
- **Private Cluster**: Restricted access to the Kubernetes API server

## 🛠️ Troubleshooting

### Useful Commands

```bash
# Get AKS credentials
az aks get-credentials --resource-group RESOURCE_GROUP --name CLUSTER_NAME

# Kubernetes Authentication
kubelogin convert-kubeconfig -l azurecli

# Check application status
kubectl get all -n time-api

# View logs
kubectl logs -f deployment/time-api -n time-api
```

## 🧹 Cleanup

To destroy all Terraform resources:

**Using GitHub Actions**: Trigger the "Destroy Infrastructure" workflow manually from the GitHub Actions tab.

**Manual Cleanup**:

```bash
cd terraform
terraform destroy
```

**Note**: This will permanently delete all Microsoft Azure resources created with `terraform apply`.

## 📝 Project Structure

```txt
self-hosted-full-stack/
├── .github/
│   └── workflows/                    # GitHub Actions CI/CD pipelines
│       ├── build.yaml                # Main deployment workflow
│       ├── destroy.yaml              # Resource cleanup workflow
│       └── integrate.yaml            # Subsequent infrastructure/deployment changes workflow
├── backend/                          # Flask API application
│   ├── app.py                        # Flask application entry point
│   ├── Dockerfile                    # Backend container image definition
│   └── requirements.txt              # Python dependencies
├── frontend/                         # Vite React application
│   ├── public/                       # Static assets
│   ├── src/                          # React source code
│   │   ├── assets/                   # Images and other assets
│   │   ├── components/               # React components
│   │   │   ├── CityCard.css          # City card styles
│   │   │   ├── CityCard.jsx          # City card component
│   │   │   ├── ClockOrbit.css        # Clock orbit animation styles
│   │   │   ├── ClockOrbit.jsx        # Clock orbit component
│   │   │   ├── Dashboard.css         # Dashboard styles
│   │   │   └── Dashboard.jsx         # Dashboard component
│   │   ├── App.css                   # Application styles
│   │   ├── App.jsx                   # Main App component
│   │   ├── index.css                 # Global styles
│   │   └── main.jsx                  # Application entry point
│   ├── .env                          # Local environment variables
│   ├── .env.production               # Production environment variables
│   ├── .gitignore                    # Frontend-specific Git ignore rules
│   ├── Dockerfile                    # Frontend container image definition
│   ├── eslint.config.js              # ESLint configuration
│   ├── index.html                    # HTML template
│   ├── nginx.conf                    # NGINX configuration for production
│   ├── package.json                  # Node.js dependencies and scripts
│   ├── README.md                     # Frontend documentation
│   └── vite.config.js                # Vite build configuration
├── screenshots/                      # Project screenshots and documentation images
├── terraform/                        # Infrastructure as Code (IaC) and automation
│   ├── bash_scripts/                 # Helper automation scripts
│   │   ├── get-aks-cred.sh           # Script to retrieve AKS credentials
│   │   ├── gh_secret.sh              # GitHub secrets management script
│   │   ├── pre-apply.sh              # Pre-apply script for Terraform backend setup
│   │   └── service_principal.sh      # Azure service principal creation script
│   ├── deploy/                       # Application deployment Terraform modules
│   │   ├── data.tf                   # Data sources for existing resources
│   │   ├── deploy.tf                 # Application deployment resources
│   │   ├── ingress.tf                # Ingress controller and routing configuration
│   │   ├── monitoring.tf             # Monitoring and observability stack (Prometheus/Grafana)
│   │   ├── netpolicy.tf              # Kubernetes network policies
│   │   ├── permissions.tf            # Azure RBAC permissions configuration
│   │   └── provision.tf              # Kubernetes cluster provisioning resources
│   ├── ssh_keys/                     # SSH keys for self-hosted runner access
│   │   ├── id_rsa                    # Private SSH key (git-ignored)
│   │   └── id_rsa.pub                # Public SSH key
│   ├── .terraform.lock.hcl           # Terraform dependency lock file
│   ├── backend.tf                    # Terraform remote state backend configuration
│   ├── cloud-init.yaml.tpl           # Cloud-init template for self-hosted GitHub runner setup
│   ├── main.tf                       # Main Terraform entry point (AKS cluster, resource groups, runner VM)
│   ├── network.tf                    # Azure networking configuration (VNet, subnets, NSG)
│   ├── outputs.tf                    # Terraform output values
│   ├── providers.tf                  # Terraform provider configurations
│   ├── terraform.tfvars.json         # Terraform variable values (auto-generated from GitHub secrets)
│   └── variables.tf                  # Terraform variable definitions
├── .gitignore                        # Root Git ignore rules
├── Dockerfile                        # Legacy/root Dockerfile (if applicable)
├── gh_secret.sh                      # Root-level GitHub secrets setup script
└── README.md                         # Project documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and commit: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 🆘 Support

If you encounter issues:

1. Check the [Troubleshooting](#️-troubleshooting) section
2. Review the GitHub Actions logs
3. Check Microsoft Azure portal for resource status
4. Open an issue in this repository

## 🔗 Useful Links

- [Microsoft Azure Documentation](https://docs.microsoft.com/en-us/azure/)
- [Docker Documentation](https://docs.docker.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Terraform Documentation](https://registry.terraform.io/)
- [Terraform Microsoft Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
- [Terraform Helm Provider](https://registry.terraform.io/providers/hashicorp/helm/latest/docs)
- [Terraform kubectl Provider](https://registry.terraform.io/providers/alekc/kubectl/latest/docs)
- [Terraform NGINX Ingress Controller Module](https://registry.terraform.io/modules/terraform-iaac/nginx-controller/helm/latest)
- [Azure Kubernetes Service Documentation](https://docs.microsoft.com/en-us/azure/aks/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

---

**Disclaimer**: This project is designed for learning and demonstration purposes. For production use, consider additional security hardening, cost optimization, and compliance requirements specific to your organization.
