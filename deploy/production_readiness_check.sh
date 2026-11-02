#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/deploy/validate_environment.sh"
"$ROOT/deploy/health_check.sh"
echo 'Infrastructure checks passed. Live production approval remains BLOCKED until broker evidence, security, backups/restore, compliance and operational tests are independently verified.'
exit 2
