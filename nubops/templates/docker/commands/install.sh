#!/bin/sh
# Source: <https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository>
set -e

# Install packages to allow apt to use a repository over HTTPS.
sudo apt-get -y install ca-certificates curl gnupg

# Add Docker’s official GPG key.
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up the repository.
echo \
  "deb [arch="$$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$$(. /etc/os-release && echo "$$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install docker.
sudo apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
