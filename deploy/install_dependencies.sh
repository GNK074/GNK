#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${GNK_INSTALL_CONFIRM:-}" == INSTALL_PACKAGES ]] || { echo 'Review host policy, then set GNK_INSTALL_CONFIRM=INSTALL_PACKAGES to install curl, gpg and python3-venv. Docker installation is operator-managed.' >&2; exit 1; }
sudo apt-get update
sudo apt-get install -y curl gpg python3-venv
