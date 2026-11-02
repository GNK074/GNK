# Profile and settings

The existing authenticated `/user/settings` route now provides a responsive GNK ALGO profile page using the requested charcoal/purple palette and original supplied artwork. Existing dashboard, broker, strategy, portfolio, risk and administration routes remain available.

## Account actions

- Full name is trimmed, 2–100 characters. Gender supports female, male, non-binary and prefer-not-to-say; existing accounts can leave it unspecified. Birth dates must be between 1900-01-01 and today. Mobile numbers use international format without spaces (for example `+919876543210`). These extra details are returned only through the authenticated self-profile API.
- Photos accept actual JPEG, PNG or WebP files, up to 2 MiB and 16 megapixels. The server decodes, orients, crops to 512×512, strips metadata and stores normalized PNG bytes in PostgreSQL. Photos require the owner's session; there are no public photo paths or filesystem uploads. Reset restores initials.
- Appearance supports Light, Carbon Black and Royal Blue. Selection applies immediately, persists in the database, and uses a local theme-only cache to avoid a flash on the next visit. Failed saves restore the previous theme. Tokens remain in HttpOnly cookies.
- Password changes require the current password and the existing strong-password policy. Password changes/recovery revoke sessions and outstanding email-change links. Reset emails use the existing SMTP recovery flow.
- Email changes require the current password and a single-use, hashed, 20-minute confirmation link sent to the new address. The original email remains active until confirmed. Confirmation revokes all sessions and outstanding recovery/verification links. A confirmation link never changes the email through a GET request.
- Session management lists the latest 100 sessions, marks this device and expired/revoked sessions, and allows revoking another owned session. Sign-out opens a keyboard-accessible native dialog with this-device/all-device choices.
- MFA setup reuses the existing authenticator enrollment flow. Existing MFA and live-trading gates remain enforced.

Registration includes full name, gender, date of birth, mobile, email, password, confirmation and both required consents. Login displays email/password, recovery link, then optional enrolled-authenticator code. Existing API registration clients remain compatible; additional demographic fields are optional at the API boundary for existing clients/accounts. Mobile ownership is not SMS-verified.

## API changes

All private endpoints require the existing cookie session. Mutations require `X-CSRF-Token`.

- `GET /api/v1/users/me`: self details, theme, photo URL and CSRF token.
- `PUT /api/v1/users/me`: name, gender, date_of_birth and mobile; returns updated user.
- `PUT /api/v1/users/me/preferences`: theme enum (`light`, `carbon_black`, `royal_blue`).
- `PUT /api/v1/users/me/avatar`: raw image bytes; `GET` serves private normalized PNG; `DELETE` resets.
- `GET /api/v1/users/me/sessions`; `DELETE /api/v1/users/me/sessions/{id}`: owner-scoped session management.
- `POST /api/v1/auth/change-email`: email/current_password; generic delivery response.
- `POST /api/v1/auth/confirm-email-change`: token proof, usable without a session.
- Existing change-password, forgot-password, logout and logout-all endpoints are reused. `logout` now revokes only the current session; `logout-all` revokes every session.

## Deploy an existing installation

This release adds migration `0003`; build the new backend and apply migrations before starting it. Preserve `.env` and secrets. From `/opt/gnk`, after pushing these changes from Windows:

```bash
git pull --ff-only
./deploy/deploy_production.sh
GNK_ENV=production ./deploy/gnk-service.sh health
```

The deployment script builds, backs up, provisions the restricted database role, migrates using the migration container, deploys and validates. Review its output before continuing if any command fails. No database-volume removal is needed.

The bundled container Nginx permits 3 MiB requests; the avatar API enforces 2 MiB. If host Nginx has a smaller request limit, set `client_max_body_size 3m;` in the existing GNK HTTPS server block, then run `sudo nginx -t && sudo systemctl reload nginx`. Keep the existing TLS/proxy settings. Confirm actual SMTP delivery of verification and recovery messages in production.

## Validation

Run `PYTHONPATH=backend python -m pytest tests -q` and `npm --prefix frontend run build`. Integration tests cover persisted details/themes, invalid dates/mobile, CSRF, private image processing, size rejection/reset, session ownership, device-only logout, email proof/replay protection and password revocation. Existing broker and paper execution tests remain part of the full suite.

A local Chromium check exercised profile saves, photo upload/reset, theme changes/reload persistence, session display, strength feedback, sign-out confirmation/Escape and successful registration submission at desktop (1440px), tablet (820px) and mobile (390px), with no horizontal overflow or browser runtime errors. This used a disposable local SQLite account and mocked email/rate-limiter dependencies, not the production deployment. Linux service and actual PostgreSQL RLS checks run in CI; they are skipped on this Windows environment when their services are absent.
