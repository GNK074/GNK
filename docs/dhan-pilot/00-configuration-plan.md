# Dhan pilot configuration plan

| Order | Owner | Document | Completion check |
| --- | --- | --- | --- |
| 1 | VM operator | [Production deployment](01-production-deployment.md) | VM checkout contains the pilot commit and public health checks pass |
| 2 | VM operator or GNK administrator | [GNK configuration and IP](02-gnk-configuration-and-ip.md) | Individual Dhan setup is available and the IP comparison returns an explainable result |
| 3 | Dhan account owner | [Connect and refresh](03-connect-and-refresh.md) | Broker identity verifies and portfolio reads return data or a valid empty result |
| 4 | Operator and account owner | [Acceptance and troubleshooting](04-acceptance-and-troubleshooting.md) | Reconnect, disconnect and expiry behavior are confirmed |

The pilot uses a single GNK backend process as its session owner. Credentials live in that process's memory for up to 15 minutes, capped by broker token expiry. Each GNK login verifies separately. A process restart requires reconnecting.

Acceptance covers the read-only pilot. Moving background workers, live execution and legacy credential storage to the new architecture is a separate cutover. The last agent-side deployment attempt ended at SSH authentication, so use the VM checks to establish the actual deployed revision.
