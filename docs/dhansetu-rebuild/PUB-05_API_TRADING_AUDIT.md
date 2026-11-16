# PUB-05 API Trading audit

GNK uses React, Vite, TypeScript, React Router and Lucide. App owns public route selection, Landing provides navigation, Logo provides brand identity and ContactUsPage handles support. Existing registration and broker setup are at /register and /user/brokers. The workspace has authentication and disclosure gates.

Dhan has implemented consent and account inspection paths, with production consent and live execution previously observed disabled. FYERS has a profile verifier. Upstox has OAuth and market-data code outside the new public onboarding path. The public page makes no claim of verified live availability for these brokers. Broker connectivity, individual account authorization and execution approvals remain separate.

The frontend is served by Nginx with a SPA fallback. PUB-05 uses a dedicated Vite HTML entry for initial-response SEO. The public page uses the existing brand, theme variables and contact workflow. No standalone terms or privacy route was found, so the page points visitors to account agreements during registration and states its own risk disclosure.
