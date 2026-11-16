# Feature parity matrix

| Reference feature | Observed behavior | GnKAlgo implementation | API required | Database required | Test status |
| --- | --- | --- | --- | --- | --- |
| Directory, search and selection | Empty-state list, broker combobox and Next observed. Search filtering unverified. | New native workspace over current catalogue | Catalogue read | Reuse registry | Pending |
| Add, edit and multiple accounts | Add flow and optional Dhan setup observed. Save, edit and multiple accounts unverified. | Owner-scoped accounts and per-broker forms | Configuration mutations | Review account labels and uniqueness | Pending |
| OAuth, reconnect and renewal | NOT VERIFIED | Reuse consent/adapter flows with per-broker capabilities | Broker-specific auth | Reuse auth state and encrypted credential rows | Pending |
| Exchange and segment management | NOT VERIFIED | Store preferences separately from broker verification | Exchange and entitlement reads | Add verified entitlement metadata if needed | Pending |
| Static IP and approvals | NOT VERIFIED | Reuse GNK approval and represent broker confirmation separately | Existing IP APIs and broker verification | Reuse IP records with scoped verification evidence | Pending |
| Disconnect, removal and audit | NOT VERIFIED | Revoke locally, use broker revocation when supported, preserve historical references | Owner-scoped disconnect and removal | Reuse account/audit records and add soft deletion if needed | Pending |
| Responsive layouts | NOT VERIFIED | Responsive GNK workspace and keyboard navigation | No | No | Pending |
