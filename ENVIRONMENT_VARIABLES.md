# Environment configuration

Use .env.example for development and .env.production.example for reviewed production setup. Never commit real .env profiles. APP_ENV is canonical; legacy ENVIRONMENT is accepted. JWT_SECRET_KEY is canonical; legacy JWT_SECRET is accepted. Keep aliases consistent. The synchronous SQLAlchemy stack intentionally uses postgresql+psycopg, not asyncpg.

Required: an independent 32+ character JWT secret and a valid FIELD_ENCRYPTION_KEY. Production also requires independent SECRET_KEY, HTTPS origins, debug=false, secure cookies, MFA, startup connectivity checks, real TLS SMTP credentials and authenticated Redis. LIVE_TRADING_ENABLED=true is rejected during configuration loading because no live execution implementation is shipped. Paper trading defaults true. CORS defaults to FRONTEND_URL and accepts an explicit comma-separated allowlist.

Pool options: DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE; REDIS_MAX_CONNECTIONS. Session lifetime options: ACCESS_TOKEN_EXPIRE_MINUTES and REFRESH_TOKEN_EXPIRE_DAYS. Field rotation: FIELD_ENCRYPTION_PREVIOUS_KEYS (comma-separated decrypt-only keys), ENCRYPTION_KEY_VERSION. JWT algorithm is restricted to HS256.

Production Compose uses file-mounted owner/runtime DB and Redis passwords: POSTGRES_PASSWORD_FILE, APP_DB_PASSWORD_FILE, REDIS_PASSWORD_FILE on the host. It overrides DATABASE_PASSWORD_FILE/REDIS_PASSWORD_FILE to container paths. DATABASE_URL has no embedded runtime password in production. These passwords cannot be replaced by hashes in a database client configuration; PostgreSQL stores SCRAM verifiers internally, while the client must have its original authentication secret. User login passwords are Argon2 hashes, and broker credentials are Fernet ciphertext.

validate_environment.sh runs validation inside a container and checks DB/Redis; infrastructure/env/validation.py can validate a host profile with --file when dependencies are installed. Error values are suppressed. Host secret-file paths and container secret-file paths differ; validate in the intended runtime context. Unused broker/monitoring/market-data variables do not activate unimplemented features.
