#!/usr/bin/env bash
# Public entry point. Resolve from this file, never the caller's directory.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/service/gnk-service.sh" "$@"
