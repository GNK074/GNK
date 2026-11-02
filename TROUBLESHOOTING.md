# Troubleshooting

Environment invalid: validate FIELD_ENCRYPTION_KEY format, independent secret lengths, production HTTPS/MFA/cookies/SMTP flags and secret-file paths. The validator suppresses values deliberately. Do not paste .env or private keys into support tickets.

PostgreSQL connection failure after migration: verify the stored password matches the existing DB role, mounted files are readable inside the appropriate containers, gnk_app exists and grants/default privileges are present. Generating a secret does not change a database password. Production startup rejects superuser/BYPASSRLS API roles.

Redis AUTH failure: coordinate server auth enablement and client secret settings, and recreate Redis only after reviewing persistent data/config. Existing Redis data is retained. Never expose Redis to the public network.

MFA enrollment required: sign in, open /mfa, add the setup key to an authenticator and confirm a fresh code. Codes cannot be replayed; use the next time step after enrollment if signing in again immediately. Keep host time synchronized. Lost-device recovery is an external controlled support process; no bypass endpoint is shipped.

Broker disabled: documentation/application review and auth registry configuration are required. Six requested brokers have no adapter implementation. Upstox has only an auth/profile adapter and is still pending real integration verification. Failed/replayed/expired state requires reconnect. Callback query codes must not be logged. Local disconnect does not guarantee provider-side token revocation.

Paper order rejected: check strategy ownership, stop state, quantity/order value, daily count, daily realized loss and position cap. Short sells are unsupported. Reusing an idempotency key with changed content returns conflict. Unknown price/market data is never fabricated.

Production approval returns 409: inspect missing/expired evidence; even all 18 attestations cannot enable missing execution/reconciliation. Readiness exit 2 is an intentional outstanding production gate, not a crash.

GitHub push from Codex may lack the Git Bash SSH agent. Push from your authenticated Windows Git Bash, then git pull --ff-only on /opt/gnk. A clean matching commit does not imply containers or DNS were deployed.
