# Risk disclosure and Contact Us release

## Implemented behavior

Successful sign-in continues to `/user/dashboard`. The dashboard and paper-trading workspace first check the authenticated server acknowledgment. A native, accessible modal locks interaction outside it. The user can scroll the complete disclosure/source, tick the acknowledgment and submit. Escape and backdrop clicks do not dismiss it. Loading failures and failed saves keep the workspace locked; retry is available. Existing profile, security, broker and emergency-stop APIs remain reachable independently of disclosure status.

The modal preserves the four statements and source wording supplied in the project brief. It labels these as historical FY 2021–22 equity F&O findings, rather than current statistics or all-equity investing. It includes the requested investor-awareness messages, official resource links and an original risk illustration. No SEBI logo, seal, affiliation or approval is asserted.

`GET /api/v1/compliance/disclosure` returns authenticated current content, ID, version and SHA-256. `GET /api/v1/compliance/disclosure/status` checks only the current user's current login. `POST /api/v1/compliance/disclosure/acknowledge` accepts only the current document ID/version/hash plus `acknowledged: true`; it requires the existing session and CSRF token. User IDs, timestamps and session IDs cannot be supplied by clients. Duplicate requests reuse a receipt. A content edit changes the hash/version automatically, even if the operator forgets to bump the release label.

Both `/api/v1/paper/orders` and `/api/v1/live/orders` enforce this requirement on the server and return HTTP 428 when absent. A browser flag cannot unlock orders. Acknowledgment does not enable live execution; all existing production/broker/risk restrictions remain in effect. The frontend rechecks on focus and every minute while visible; order submission always checks the server immediately.

Migration `0004` stores owner, login session, disclosure ID/version/hash, server acknowledgment/creation times and policy window. PostgreSQL FORCE RLS limits visibility to the owner and insertion to a matching owned session. Runtime receipt rows are append-only: there are no UPDATE or DELETE policies. The existing audit log also records acknowledgment. No existing receipts or users are removed by this migration.

## Frequency and regulatory review

The implemented GNK platform policy requires acknowledgment on **each new login**, plus each new fixed UTC policy window (24 hours by default). Refreshing a page or rotating a refresh token does not create a new login. `DISCLOSURE_VERSION` identifies the release, and `DISCLOSURE_MAX_AGE_HOURS` (1–168) defines the additional window. A window boundary can require a fresh acknowledgment sooner than that maximum. Policy changes require operator review; this is not a determination of which SEBI obligations apply to GNK.

Sources reviewed on 2026-11-02:

- [SEBI, May 19, 2023, circular 2023/73](https://www.sebi.gov.in/legal/circulars/may-2023/risk-disclosure-with-respect-to-trading-by-individual-traders-in-equity-futures-and-options-segment_71426.html).
- [SEBI, January 25, 2023 study announcement](https://www.sebi.gov.in/media/press-releases/jan-2023/sebi-underlines-the-need-for-analysis-and-disclosure-of-risks-of-trading-in-fando_67542.html).
- [SEBI, October 1, 2026 Project Jagrook circular](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1790852162769.pdf): changes website/stock-broker-app display arrangements from November 1, 2026, including alternate-day displays for broker trading apps. The brief's older risk popup alone must not be represented as current compliance certification.
- [Official SEBI investor-awareness resources](https://investor.sebi.gov.in/).

The homepage now displays an original investor-awareness summary and official resource link in addition to the mandatory GNK authenticated gate. The summary is not an authorized reproduction of SEBI campaign artwork. Obtain compliance review of entity status, broker-versus-technology-provider applicability, exact current campaign material, required placements/scheduling, approved wording, evidence retention and trademark permissions before representing the site as regulator-compliant. The requested first risk statement broadens the original study's equity F&O scope; the modal keeps the supplied wording and adds an explicit scope note for review.

## Contact page and publication controls

Public routes `/contact-us`, `/contact-us/` and `/contact` use the existing brand/theme. Homepage and workspace footers link to Contact Us. Four responsive columns provide company information, the four requested service destinations, six legal/help destinations and contact information. Security notice, investor disclaimer and social-link components are included. The public configuration comes from `GET /api/v1/public/contact`; no secret settings are returned.

The supplied numbers, emails and five social URLs are implemented exactly, but unpublished by default because authorization has not been verified. Set `CONTACT_CHANNELS_VERIFIED=true` only after confirming ownership/authorization of all listed channels. A local test preview enables this flag solely to exercise link rendering; it is not evidence of business authorization.

The Research Analyst registration claim requires `COMPANY_REGISTRATION_VERIFIED=true`, the verified `COMPANY_LEGAL_NAME` and `COMPANY_SEBI_REGISTRATION` (`INH` plus nine digits). Until then, the page describes platform/technical services and makes no registration claim. BASL wording requires verified registration plus `COMPANY_BASL_APPLICABLE=true` and `COMPANY_BASL_MEMBERSHIP`. Configuration flags record operator attestation; they do not independently check registration status.

`COMPANY_OFFICE_ADDRESS_VERIFIED=true` and the full `COMPANY_OFFICE_ADDRESS` enable the Google Maps search link. Until then, only the supplied Bangalore 560049 location label appears; no street address or map pin is invented. Phone links use `tel:`, email links use `mailto:`, and external/social links have `noopener noreferrer`.

The provided service/legal URLs are external anchors to `www.gnkalgo.com`; their destination content is not invented in this release. Browser tests check exact hrefs, not ownership or availability of remote destinations. Those pages could not be independently fetched in this environment and must be checked before public release. This release does not provide substantive service agreements, investor-charter or grievance-policy documents absent from the brief.

## Deployment

Preserve the existing `.env`, passwords and mounted secrets. Review the new example settings and add approved values to the server environment. From `/opt/gnk` after pushing/syncing the code:

```bash
git pull --ff-only
./deploy/deploy_production.sh
GNK_ENV=production ./deploy/gnk-service.sh health
```

The deployment script builds, backs up, provisions runtime permissions, migrates to `0004`, deploys and validates. Apply migration before the new backend starts. Do not delete data volumes. After release, test a new login, acknowledgment, page refresh and sign-out/new-login cycle. Review policy/source updates with the compliance owner rather than changing browser storage.

## Validation

Run `PYTHONPATH=backend python -m pytest tests -q` and `npm --prefix frontend run build`. New API tests cover authentication/CSRF, duplicate acknowledgments, extra owner fields, version/hash changes, policy windows, session/user isolation, order blocking, and conditional contact publication. Existing order/risk/tenant tests now acknowledge through the real API before trading. The PostgreSQL CI check includes owner-only receipt reads/inserts, rejected foreign-session inserts and append-only enforcement.

Local Chromium checks cover locked modal/Escape, readable source, required checkbox, failed save/retry, persisted receipt, refresh without duplicates, new-login repetition, phone/email/social/service hrefs and responsive desktop/tablet/mobile views. The preview uses disposable SQLite users and mocked email/rate-limit dependencies. PostgreSQL RLS and Linux service checks require their CI environments and are not claimed as locally executed.
