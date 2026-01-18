#cloud-config
package_update: true
package_upgrade: true
packages:
  - curl
  - unzip
  - jq
  - git
  - apt-transport-https
  - ca-certificates
  - gnupg
  - lsb-release
  - software-properties-common

runcmd:
  # --- Create githubrunner user ---
  - |
    useradd -m -s /bin/bash githubrunner && \
    echo "githubrunner ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/githubrunner
  
  # --- Install Docker ---
  - |
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io

  # Add user to docker group
  - usermod -aG docker githubrunner

  # Force group membership immediately without login
  - gpasswd -a githubrunner docker

  # Make sure Docker is fully up
  - |
    systemctl enable docker && \
    systemctl start docker && \
    until docker info >/dev/null 2>&1; do sleep 2; done

  # --- Install Terraform ---
  - |
    curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list && \
    apt update && apt install -y terraform

  # --- Install kubectl ---
  - |
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256" && \
    echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

  # --- Install Helm ---
  - |
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-4 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh

  # --- Install Node.js ---
  - |
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt install -y nodejs

  # --- Set up GitHub Actions Runner ---
  - |
    mkdir -p /home/githubrunner/actions-runner && \
    cd /home/githubrunner/actions-runner && \
    curl -o actions-runner-linux-x64-2.330.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.330.0/actions-runner-linux-x64-2.330.0.tar.gz && \
    echo "af5c33fa94f3cc33b8e97937939136a6b04197e6dadfcfb3b6e33ae1bf41e79a  actions-runner-linux-x64-2.330.0.tar.gz" | shasum -a 256 -c && \
    tar xzf ./actions-runner-linux-x64-2.330.0.tar.gz && \
    chown -R githubrunner:githubrunner /home/githubrunner/actions-runner && \
    su - githubrunner -c "cd ~/actions-runner && ./config.sh --url https://github.com/VictortheGreat7/digital-ocean-full-stack --token ${github_runner_token} --unattended"

  # --- Install doctl and initialize it ---
  - |
    cd /home/githubrunner && \
    wget https://github.com/digitalocean/doctl/releases/download/v1.146.0/doctl-1.146.0-linux-amd64.tar.gz && \
    tar xf /home/githubrunner/doctl-1.146.0-linux-amd64.tar.gz && \
    mv /home/githubrunner/doctl /usr/local/bin && \
    doctl auth init -t ${do_api_token}

  # ---  Start the GitHub Actions Runner service ---
  - |
    cd /home/githubrunner/actions-runner && \
    ./svc.sh install githubrunner && \
    ./svc.sh start

power_state:
  mode: reboot
  message: Rebooting for kernel upgrade
  timeout: 10
  condition: true

final_message: "GitHub Runner VM setup complete!"
