# Individual broker setup

Users supply their own individual API credentials, never a shared GNK platform session. Seven code-level inspection flows are available by default unless INDIVIDUAL_BROKER_SETUP_ENABLED=false or an explicit operator integration policy blocks that broker. These are real outbound provider requests; tests use HTTP fixtures rather than real customer credentials. No order API is called. Real provider acceptance and customer authorization have not been tested in this environment.

## Broker-specific flows

- Dhan: Dhan client ID and DhanHQ access token generated in Dhan Web. GET profile validates identity and reported expiry. Official documentation: https://dhanhq.co/docs/v2/authentication/ . Dhan distinguishes individual and partner applications; this flow does not claim partner approval.
- Zerodha: own Kite API key, access token and Zerodha user ID. GET user/profile validates identity. Follow the documented broker login/request-token exchange yourself to obtain the token. Reference: https://kite.trade/docs/connect/v3/user/ . Daily token boundary is modeled at 06:00 Asia/Kolkata.
- Upstox: own access token and Upstox user ID. GET profile validates active status and identity. Reference: https://upstox.com/developer/api-documentation/authentication/ and https://upstox.com/developer/api-documentation/get-token/ . The daily boundary is 03:30 Asia/Kolkata. Existing operator-reviewed Upstox OAuth remains a separate path; the individual form does not share platform credentials.
- FYERS: own App ID, access token and FYERS client ID. GET profile validates identity. Individual apps are for their creator's own account, not other customers. References: https://fyers.in/api-docs/v3/api/authentication/individual-app and https://fyers.in/api-docs/v3/api/account/profile . Daily boundary is modeled at 06:30 Asia/Kolkata.
- Angel One: own SmartAPI API key, JWT access token and client code. The operator must set BROKER_EGRESS_IP to the actual VM API egress IP; the local IP/MAC headers are derived from the running server. GET profile validates identity. References: https://smartapi.angelone.in/docs and https://github.com/angel-one/smartapi-python . The local daily boundary is midnight Asia/Kolkata. No broker PIN or OTP is accepted.
- 5paisa: own AppKey, API UserId, API encryption key, fresh OAuth RequestToken and expected ClientCode. The server exchanges the request token and compares the provider-returned identity; consumed request tokens are not stored. Reference: https://xstream.5paisa.com/dev-docs/user-authentication-system/access-token . The local session deadline is 23:59 Asia/Kolkata; reconnect requires new authorization material.
- ICICI Direct: own Breeze AppKey, API_Session from official login and expected idirect_userid. CustomerDetails validates identity and returns the broker session token. Reference: https://api.icicidirect.com/breezeapi/documents/index.html . Broker token lifetime is not assumed; a one-hour local deadline requires reconnect. This does not implement signed trading APIs.

Kotak Neo, Alice Blue, Shoonya, Motilal Oswal and Sharekhan remain candidates without implemented connection validators. Their setup pages explicitly report that status and collect no credentials. No badge is changed to connected until a supported provider validation succeeds.

## Application APIs

GET /api/v1/brokers returns setup metadata and independent flags: setup_available, individual_available and auth_available (the pre-existing operator OAuth path). GET /api/v1/brokers/{broker}/setup provides fields, instructions, official URLs and any operator blocker. POST /api/v1/brokers/{broker}/individual accepts credentials plus ownership/individual-terms attestations, scoped exclusively to the authenticated user. Unknown fields, passwords/PINs/OTPs, invalid identity and denied provider requests are rejected.

Connection storage uses the existing user/account-bound encrypted envelope. Same-owner reconnect updates that account; a different GNK user cannot link or replace it. State, expiry basis and last verification time are returned without secrets. Local session deadlines are not a claim of continuous remote health. Public connections and dashboard counts exclude locally expired sessions. Global verification badges have been replaced by accurate setup/connection states.

All required fields are entered through the HTTPS app. Do not paste tokens into chat, shell arguments, screenshots, Git or browser localStorage. No automatic OAuth callback is invented for token-entry flows. Register callback URLs only as required by the broker's actual individual authorization procedure.

## Deploy the code update

No database migration is added in this change. Push the updated Windows source, then pull the same commit on /opt/gnk. Preserve existing .env, secrets and volumes. Optional operator settings: INDIVIDUAL_BROKER_SETUP_ENABLED=true and BROKER_EGRESS_IP=<actual public egress IP> (required for Angel One). Build both frontend and backend; a frontend-only deploy cannot enable the API handlers. After deployment each user opens Brokers & Exchanges, selects their broker, follows the official setup guide, supplies their own session material and verifies their account.

This change enables account inspection/setup, not real-money execution, partner approval, redistribution rights, funds/holdings synchronization, automatic session renewal or broker sandbox approval. The existing live approval and risk gates remain enforced.
