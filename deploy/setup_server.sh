#!/usr/bin/env bash
set -Eeuo pipefail
printf 'CPU: '; getconf _NPROCESSORS_ONLN
free -h
df -h /
command -v docker >/dev/null && docker version
command -v docker >/dev/null && docker compose version
echo 'Read-only server audit completed. No packages, firewall rules, SSH settings, certificates or existing services were changed.'
