#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
trap 'printf "GNK service command failed (line %s). See: ./deploy/gnk-service.sh logs\n" "$LINENO" >&2' ERR

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'USAGE'
GNK ALGO service manager
Usage: ./deploy/gnk-service.sh COMMAND [SERVICE ...]

  start        Create/start all services and wait for readiness
  stop         Stop all services; preserve containers and database volumes
  build        Build frontend/backend images without starting services
  deploy       Build, create/update services and wait for readiness
  status       Display containers, readiness and all application URLs
  logs         Follow logs (optionally select services, e.g. logs backend nginx)
  health       Check every container and the HTTP application/API endpoints
  urls         Display public, admin, API and internal service addresses
  help         Show this help

Configuration (environment variables):
  GNK_ENV             development or production; defaults to .env ENVIRONMENT
  GNK_PUBLIC_URL      URL to display/probe; defaults to .env FRONTEND_URL
  GNK_HEALTH_URL      Optional separate HTTP probe origin (e.g. local proxy)
  GNK_WAIT_TIMEOUT    Readiness timeout in seconds (default: 180)
  GNK_LOG_TAIL        Number of lines per service (default: 200)
  GNK_LOG_FOLLOW      Set to 0 for a one-time log snapshot (default: 1)

Production uses both Compose files. Configure HTTPS termination separately.
No command deletes volumes or changes Git source. Dev startup migrates in the backend; production uses deploy/migrate_database.sh. Stop does not cancel existing broker orders.
USAGE
}

# Read simple dotenv assignments as data. Never source/eval a secrets file.
dotenv() {
  local wanted="$1" line value
  [[ -f "$ROOT/.env" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    if [[ "$line" == "$wanted="* ]]; then
      value="${line#*=}"
      if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; fi
      printf '%s' "$value"
      return 0
    fi
  done < "$ROOT/.env"
}

COMMAND="${1:-help}"
[[ $# -eq 0 ]] || shift
case "$COMMAND" in start|stop|build|deploy|status|logs|health|urls|help|-h|--help) ;; *) usage >&2; die "Unknown command: $COMMAND" ;; esac
if [[ "$COMMAND" == help || "$COMMAND" == -h || "$COMMAND" == --help ]]; then usage; exit 0; fi
[[ "$COMMAND" == logs || $# -eq 0 ]] || die 'Only logs accepts service arguments.'

MODE="${GNK_ENV:-${APP_ENV:-${ENVIRONMENT:-$(dotenv APP_ENV)}}}"
MODE="${MODE:-$(dotenv ENVIRONMENT)}"
MODE="${MODE:-development}"
[[ "$MODE" == development || "$MODE" == production ]] || die 'GNK_ENV must be development or production.'
PUBLIC_URL="${GNK_PUBLIC_URL:-${FRONTEND_URL:-$(dotenv FRONTEND_URL)}}"
PUBLIC_URL="${PUBLIC_URL:-http://localhost:8080}"
PUBLIC_URL="${PUBLIC_URL%/}"
PROBE_URL="${GNK_HEALTH_URL:-$PUBLIC_URL}"
PROBE_URL="${PROBE_URL%/}"
for url in "$PUBLIC_URL" "$PROBE_URL"; do
  [[ "$url" == http://* || "$url" == https://* ]] || die 'Application origins must start with http:// or https://.'
  [[ "$url" != *'@'* && "$url" != *$'\n'* && "$url" != *'?'* && "$url" != *'#'* ]] || die 'Origins must not contain credentials, queries, fragments or newlines.'
done
WAIT="${GNK_WAIT_TIMEOUT:-180}"
TAIL="${GNK_LOG_TAIL:-200}"
[[ "$WAIT" =~ ^[1-9][0-9]*$ && "$TAIL" =~ ^[0-9]+$ ]] || die 'Wait timeout and log tail must be valid integers.'

urls() {
  printf '\nGNK ALGO URLs (%s)\n' "$MODE"
  local path
  for path in / /contact-us /mfa /forgot-mfa /mfa-recovery /login /register /forgot-password /verify /reset /user/dashboard /user/broker-and-exchanges /user/settings /user/security /user/strategies /user/portfolio /user/dhan /api/v1/dhan/status /api/v1/dhan/instruments /user/live-orders /tradedetails/orders /tradedetails/client-trade-history /tradedetails/signals /api/v1/tradedetails/orders /api/v1/tradedetails/client-trade-history /api/v1/tradedetails/signals /api/v1/portfolio/summary /api/v1/portfolio/accounts /api/v1/portfolio/holdings /api/v1/portfolio/positions /api/v1/portfolio/funds /api/v1/portfolio/sync-status /api/v1/live/readiness /markets /markets/watchlist /markets/instruments /markets/history /markets/market-status /api/v1/marketdata/status /api/v1/marketdata/health /api/v1/marketdata/sync-status /admin /docs /openapi.json /api/v1/health /api/v1/public/contact /api/v1/compliance/disclosure /api/v1/compliance/disclosure/status /api/v1/brokers/connections /api/v1/strategies /api/v1/orders /api/v1/positions /api/v1/risk/configuration /api/v1/admin/dashboard /api/v1/admin/users /api/v1/admin/audit-logs /api/v1/admin/system-health; do
    printf '  %s%s\n' "$PUBLIC_URL" "$path"
  done
  printf '\nAdmin URLs require an authenticated administrator; verification/reset links require emailed tokens.\n'
  printf 'All API routes and schemas: %s/docs\n' "$PUBLIC_URL"
  if [[ "$MODE" == development ]]; then printf 'Development email inbox (server loopback): http://127.0.0.1:8025\n'; fi
  printf 'Internal Docker addresses (not public URLs):\n  frontend:80  backend:8000  postgres:5432  redis:6379  mailpit:1025\n'
  printf 'Production requires an external HTTPS reverse proxy; live placement requires explicit server activation and broker/account approvals.\n\n'
}
if [[ "$COMMAND" == urls ]]; then urls; exit 0; fi

command -v docker >/dev/null 2>&1 || die 'Docker is not installed or not on PATH.'
docker compose version >/dev/null 2>&1 || die 'Docker Compose v2 is required (v2.24.4+ for production).'
docker info >/dev/null 2>&1 || die 'Docker daemon is unavailable or your account lacks Docker access.'
[[ -f "$ROOT/.env" ]] || die 'Missing .env. Copy .env.example to .env and configure secrets first.'
COMPOSE=(docker compose --project-directory "$ROOT" --env-file "$ROOT/.env" -f "$ROOT/docker-compose.yml")
if [[ "$MODE" == production ]]; then COMPOSE+=(-f "$ROOT/docker-compose.prod.yml"); fi
"${COMPOSE[@]}" config --quiet
SERVICES="$("${COMPOSE[@]}" config --services)"
[[ -n "$SERVICES" ]] || die 'Compose configuration contains no services.'

validate_secrets() {
  local key value
  for key in JWT_SECRET POSTGRES_PASSWORD; do
    if [[ "$key" == POSTGRES_PASSWORD && "$MODE" == production ]]; then continue; fi
    value="${!key:-}"
    [[ -n "$value" ]] || value="$(dotenv "$key")"
    if [[ "$key" == JWT_SECRET ]]; then
      preferred="${JWT_SECRET_KEY:-$(dotenv JWT_SECRET_KEY)}"
      [[ -z "$preferred" ]] || value="$preferred"
    fi
    [[ -n "$value" && "$value" != *replace-with* ]] || die "Configure $key before building or starting the application."
    if [[ "$key" == JWT_SECRET && ${#value} -lt 32 ]]; then die 'JWT_SECRET must have at least 32 characters.'; fi
  done
}

container_checks() {
  local service ids id state result=0
  printf '\nContainer readiness\n'
  while IFS= read -r service; do
    [[ -n "$service" ]] || continue
    ids="$("${COMPOSE[@]}" ps --all --quiet "$service")"
    if [[ -z "$ids" ]]; then printf '  FAIL %-12s not created\n' "$service"; result=1; continue; fi
    while IFS= read -r id; do
      state="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$id")"
      case "$state" in
        'running healthy') printf '  PASS %-12s %s\n' "$service" "$state" ;;
        'running no-healthcheck') printf '  WARN %-12s running; no Docker readiness probe\n' "$service" ;;
        *) printf '  FAIL %-12s %s\n' "$service" "$state"; result=1 ;;
      esac
    done <<< "$ids"
  done <<< "$SERVICES"
  return "$result"
}

health() {
  local result=0 path code
  container_checks || result=1
  command -v curl >/dev/null 2>&1 || { printf '  FAIL curl is required for HTTP health probes\n' >&2; return 1; }
  printf '\nHTTP probes: %s\n' "$PROBE_URL"
  for path in / /api/v1/health; do
    if code="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --connect-timeout 5 --max-time 15 "$PROBE_URL$path")" && [[ "$code" == 200 ]]; then
      printf '  PASS %s (HTTP %s)\n' "$path" "$code"
    else
      printf '  FAIL %s (HTTP %s)\n' "$path" "${code:-unreachable}"; result=1
    fi
  done
  return "$result"
}

case "$COMMAND" in
  start)
    validate_secrets
    "${COMPOSE[@]}" up --detach --wait --wait-timeout "$WAIT"
    urls
    health
    ;;
  stop)
    "${COMPOSE[@]}" stop
    printf 'Services stopped. Database and Redis volumes preserved.\n'
    ;;
  build)
    validate_secrets
    "${COMPOSE[@]}" build
    printf 'Build completed. No services started.\n'
    ;;
  deploy)
    validate_secrets
    "${COMPOSE[@]}" build
    "${COMPOSE[@]}" up --detach --wait --wait-timeout "$WAIT"
    urls
    health
    ;;
  status)
    "${COMPOSE[@]}" ps --all
    urls
    container_checks
    ;;
  logs)
    for selected in "$@"; do
      found=0
      while IFS= read -r service; do if [[ "$selected" == "$service" ]]; then found=1; break; fi; done <<< "$SERVICES"
      [[ "$found" == 1 ]] || die "Unknown log service: $selected"
    done
    ARGS=(logs --tail "$TAIL" --timestamps)
    [[ "${GNK_LOG_FOLLOW:-1}" == 0 ]] || ARGS+=(--follow)
    "${COMPOSE[@]}" "${ARGS[@]}" "$@"
    ;;
  health) health ;;
esac
