# GNK Algo Dhan integration

The official pinned SDK supplies payload builders and binary parsers. GNK owns authentication, encrypted credentials, tenant isolation, bounded transport, personal socket lifecycle, risk, durable execution and reconciliation.

- `client.py`: read-only default SDK boundary; explicit internal execution capability.
- `routes.py`, `analytics.py`: account and research reads; super-admin bounded master sync.
- `instruments.py`: official Indian equity metadata in the DHAN namespace.
- `authentication.py`, `models.py`: session-bound, one-time encrypted application consent.
- `streams.py`, `stream_routes.py`: private worker leases, GNK tickets and sanitized feeds.
- `execution.py`: Dhan adapter for the existing GNK order-intent/risk/reconciliation workflow.

See root DHAN_TECHNICAL_ASSESSMENT.md, docs/dhan-sdk-feature-map.json and DHAN_INTEGRATION_GUIDE.md. Advanced order families, order modification, global stocks and deep feeds remain unavailable.
