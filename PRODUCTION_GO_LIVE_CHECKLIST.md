# Production go-live checklist

Current decision: BLOCKED for real-money trading.

Application: frontend build, account/MFA flows, admin authorization, three-user API isolation and paper controls must pass. Check migration 0002 on a restored database. The local test record is in VALIDATION.md; do not treat unexecuted CI as passed.

Infrastructure: verify Oracle capacity, restricted DB runtime role, forced RLS with actual PostgreSQL, authenticated Redis, real SMTP delivery, public DNS, HTTPS/certificate renewal, private internal network, firewall/SSH policy, process restart, monitoring/alerts, encrypted off-host backup and successful restoration drill. Obtain explicit production deployment approval after reviewing these items.

For EACH broker require all 18: registered API application; necessary platform/partner approval; permissions; exact callback; tested auth; multi-user isolation; encrypted credentials; state expiry/replay protection; account ownership; tested lifecycle; authorized WebSocket subscriptions; static IP requirements; tested place/modify/cancel; order/fill/position reconciliation; risk controls; real emergency cancellation; security/regulatory review; monitoring/backup/recovery evidence.

Each item requires dated reviewer evidence with a hash/reference and expiry. No partial approval, no automatic count override, no shared customer credentials, no live order without explicit customer authorization, no assuming app registration proves partner permission. The current software deliberately has no live approval path while execution/reconciliation remain absent.
