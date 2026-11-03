# Sign-out fix

This change fixes reproducible sign-out failures with an expired access JWT, another tab's rotated CSRF token, or incomplete MFA enrollment. No trading, market-data activation, environment, broker credential, order or position settings are changed. No database migration is required.

## Changes

- Logout authenticates revocation using a valid server refresh session, or a still-valid access cookie if the refresh cookie is absent. A valid session-bound CSRF token remains mandatory. Signing out grants no additional workspace access or MFA privileges.
- GET /api/v1/auth/session returns only the current session's CSRF proof. It does not extend or rotate tokens, and has the existing no-store response policy. Origin checks reject unrelated browser origins while allowing a same-origin host served through the reverse proxy.
- This device revokes only the current session and clears the matching HttpOnly cookies. Already expired/revoked sessions can clear local cookies idempotently.
- All devices revokes all sessions of the authenticated owner; other users are unaffected. If no valid identity remains, it requires sign-in rather than falsely claiming to revoke other devices.
- The frontend obtains a current CSRF proof specifically for sign-out. It retries only a CSRF-rejected logout once; trading and other API mutations are never replayed by this helper.
- Sign-out errors appear inside the confirmation dialog. Repeated clicks are guarded. Settings and sidebar buttons share the same behavior, and MFA enrollment now has a sign-out button.
- Other tabs on the same origin redirect through a token-free storage notification. Other devices are blocked by server revocation immediately and their app view checks session validity on focus/visibility and every 30 seconds while visible. Transient network errors do not falsely sign out a valid session.
- Session revocation locks the owning user before the session, matching login/recovery lock order.

## Verification

Nine focused backend regression tests pass: access-token expiry, owner-only all-device revocation, MFA restrictions, CSRF/origin rejection, CSRF rotation, expired-session behavior, access-only logout, same-origin www handling and preservation of live-execution flags.

Headless Chromium against an actual local FastAPI/SQLite fixture passed sidebar and settings sign-out, expired access logout, independent browser-device isolation, all-device revocation, cross-tab redirect, remote-device redirect on focus, CSRF rotation recovery, MFA screen sign-out and visible server-error handling. No real account or broker action was used.

TypeScript/Vite production build passed. Full backend regression suite: 133 passed, 15 skipped (Linux/PostgreSQL-dependent checks).

## Deploy together without changing live flags

Once this commit is available on the deployment branch, run on the VM:

```bash
cd /opt/gnk
(
  set -e
  git pull --ff-only
  dc=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
  "${dc[@]}" build backend frontend
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 180 backend frontend
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 60 nginx
  GNK_ENV=production ./deploy/gnk-service.sh health
)
```

Deploy backend and frontend together because the new sign-out flow uses the new session-proof endpoint. Recreating Nginx refreshes its backend/frontend container address resolution. Keep the existing .env, live enablement, credentials and database/Redis volumes unchanged. Execution/market workers do not require recreation for this authentication-only fix.

Verify through two browser sessions: This device should retain the other login; All devices should block both sessions. Test logout after access-token expiry and confirm that a failed network request leaves a clear retryable dialog error.

Signing out revokes web sessions. It does not cancel broker orders or close positions.
