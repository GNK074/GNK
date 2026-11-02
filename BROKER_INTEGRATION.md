# Current broker integration status

See INDIVIDUAL_BROKER_SETUP.md for the seven per-user account-validation flows, exact required fields, official references and remaining broker candidates. Individual setup is now available without shared platform credentials where its validator is implemented and operator policy permits it. Each customer must supply valid material for their own registered API application/session; the server checks the provider-returned identity and encrypts stored credentials.

Upstox's existing operator-reviewed OAuth/code/profile adapter remains separate from individual token entry. Other providers' complete browser callback/token-renewal implementations are not claimed by these manual inspection flows. The official documentation and commercial/application requirements differ by broker; account inspection is not trading or partner authorization.

The central OAuth state manager retains hashed single-use state, expiry, encrypted per-owner storage, ownership checks and callback replay prevention. Individual direct credentials are accepted only through authenticated, CSRF-protected API writes with explicit ownership/individual-terms confirmation and matching read-only provider identity.

The 18-requirement broker production gate remains in place. Live order execution is unavailable and cannot be enabled by an account-connection badge, an environment toggle or a frontend request. Provider testing with real authorized accounts, operational approvals, market-data licensing, static IP rules and live execution/reconciliation remain outstanding.
