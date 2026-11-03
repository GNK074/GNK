# Authenticator setup, recovery, and workspace appearance

## User-facing changes

- Login now labels the field **Authenticator code** and provides **Forgot MFA?** at `/forgot-mfa`.
- Successful email verification redirects to `/login?verified=1` with a confirmation message. The verification token is removed from the current history entry. Failed or expired links retain an error and sign-in link; opening a link alone does not mutate the account.
- `/mfa` generates a private QR code from the backend's provisioning URI using bundled `qrcode.react`. It runs entirely in the browser; no external QR service receives the setup key. Manual setup remains available with SHA-1, six digits and a 30-second period. Confirmation still requires a valid authenticator code.
- Enrollment displays ten single-use recovery codes once. Users must confirm they saved them before continuing. Existing enrolled users can generate replacement recovery codes in Profile & Settings using their current password and a fresh authenticator code. New generation invalidates old codes and pending recovery requests.
- Authenticated `/user/*` and `/admin` pages now use only the saved Light, Carbon Black or Royal Blue appearance. The artwork background remains on public/authentication pages.

## Recovery flow

1. Open **Forgot MFA?** and provide the account email/password and a saved recovery code, if available. Responses are generic to avoid disclosing account eligibility. Invalid passwords/codes send no email.
2. An eligible request emails a random, hashed, 20-minute confirmation link. The supplied recovery code is consumed at request creation. Only one pending request per account remains valid. No MFA state changes occur yet.
3. The user explicitly confirms the email link at `/mfa-recovery`. With valid password, recovery-code proof and email proof, recovery completes. Without a code, email is confirmed and independent super-administrator approval is required within 24 hours; MFA remains enabled while waiting. The confirmation token cannot be reused.
4. A super administrator opens Administration → MFA recovery review, independently verifies identity/account ownership, and explicitly attests that verification. Approval also requires the administrator's password and a fresh authenticator code. Self-approval and super-administrator target recovery are excluded from this path. Regular administrators cannot review or approve these requests.
5. Completion revokes all existing sessions, recovery/reset/verification links and remaining backup codes. It removes the old authenticator and forces enrollment of a new one at the next password sign-in, even if optional MFA is otherwise configured. A completion notice is emailed. No trading/workspace access is granted until new enrollment succeeds.

For a super administrator who has lost both the authenticator and all recovery codes, use an independently verified operator-assisted account recovery procedure. This release does not add an unauthenticated override or automatically trust email alone. Existing accounts do not automatically have recovery codes; they must generate them after a valid MFA sign-in, or use the reviewed recovery path.

Password resets/changes and verified email changes invalidate pending MFA recovery requests. Session, account and CSRF checks remain in force. Recovery codes are random 80-bit values stored only as owner-bound SHA-256 hashes. Email proof tokens are hashed. Setup/recovery keys never enter localStorage. Frontend and proxy Nginx access logs omit query strings so email-link tokens are not recorded there.

## API endpoints

- `GET /api/v1/auth/mfa/status`
- `POST /api/v1/auth/mfa/setup`
- `POST /api/v1/auth/mfa/confirm` returns recovery codes once on successful enrollment.
- `GET /api/v1/auth/mfa/recovery/codes/status` returns the count only.
- `POST /api/v1/auth/mfa/recovery/codes` requires password, fresh code and authenticated CSRF-protected session.
- `POST /api/v1/auth/mfa/recovery/request` requires email/password; recovery_code is optional.
- `POST /api/v1/auth/mfa/recovery/confirm` requires the email token.
- `GET /api/v1/admin/mfa-recovery/requests` lists pending email-verified requests for super administrators.
- `POST /api/v1/admin/mfa-recovery/requests/{id}/approve` requires password, fresh code, CSRF and `identity_verified: true`.

The recovery-code table has forced PostgreSQL owner RLS. Recovery requests use explicit server-side ownership/proof and admin checks, as pre-authentication requests must be resolvable by email-token hash; they are not exposed through a user-supplied ID endpoint.

## Deployment

Migration **0005** adds the recovery tables and `users.mfa_reenroll_required` without removing accounts. Preserve `.env`, existing keys, secrets and database volumes. Sync the source, take a backup and run the existing production deployment workflow, which rebuilds the migrator before upgrading:

```bash
cd /opt/gnk
./deploy/deploy_production.sh
GNK_ENV=production ./deploy/gnk-service.sh health
```

Do not start the new backend against an unmigrated schema. Keep real SMTP configured: sending verification and recovery messages is essential. App-level SQL changes and backups require the existing operator procedures. Readiness checks reject a schema older than migration 0005.

## Validation

The backend suite covers enrollment/replay, hashed single-use code creation, generic recovery requests, invalid passwords/codes, expired or replayed links, password-change invalidation, administrator authorization/step-up/attestation, session revocation and mandatory re-enrollment. The migration check upgrades an existing database and compares its schema to ORM metadata. PostgreSQL RLS checks run in CI when that service is available.

A local Chromium walkthrough exercised QR rendering and real TOTP confirmation, saving recovery codes, password/code/email recovery, forced new enrollment, verification-to-login navigation, selected workspace theme without artwork, and mobile recovery layout. It used disposable local test accounts with mocked SMTP/rate-limit services; production SMTP and live identities were not exercised.
