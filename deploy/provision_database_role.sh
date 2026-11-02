#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
"${COMPOSE[@]}" exec -T postgres sh /opt/gnk/provision-app-role.sh
