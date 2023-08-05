#!/bin/sh
# Source: <https://docs.docker.com/engine/install/linux-postinstall/>
set -e

if [ "${sudo}" == "False" ]; then
  # If necessary, create the docker group.
  sudo groupadd --force docker

  # Add your user to the docker group.
  sudo usermod -aG docker $$USER

  # Activate the changes to groups.
  newgrp docker

  sudo chown -fR "$USER":"$USER" "HOME"/.docker
  sudo chmod -fR g+rwx "$HOME/.docker"

  # Print "hello world" via docker.
  docker run hello-world
fi

# Write default docker configuration.
if [ "${skip_demaon_json}" == "False" ]; then
  DEMON_JSON_FILE="/etc/docker/daemon.json"
  if [ -e "$$DEMON_JSON_FILE" ]; then
    echo "$${DEMON_JSON_FILE}: already exists, keeping it"
  else
    echo '{"log-driver": "local"}' | sudo tee "$$DEMON_JSON_FILE" > /dev/null
  fi
fi

# Start docker service on boot.
if [ "${skip_service}" == "False" ]; then
  sudo systemctl enable docker.service
  sudo systemctl enable containerd.service
fi
