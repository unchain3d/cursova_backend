#!/bin/bash
set -x

mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan -H 136.114.207.80 >> ~/.ssh/known_hosts

ssh ubuntu@136.114.207.80 "sudo users" || true

export DOCKER_HOST=ssh://ubuntu@136.114.207.80

docker compose build backend
docker compose up -d backend

echo "Checking status"
docker compose ps

echo "Deployed successfully"