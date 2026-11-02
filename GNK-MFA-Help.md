# Fresh MFA codes fail: diagnostic steps

The supplied `date -u` output shows only the VM's reported time. It does not show NTP state or prove the authenticator uses the matching key.

`GNK-MFA-Diagnose.sh` runs against the existing `/opt/gnk` Docker installation without needing a new backend image. Copy it to the VM and run `bash GNK-MFA-Diagnose.sh`. It prompts for the login email locally and prints only clock/NTP and MFA flags. It never requests or outputs an authenticator code, setup key, encrypted key or password, and makes no database changes. Share only the resulting diagnostic flags.

Interpretation:

- `account_found: false`: check the exact login account locally.
- `setup_key_readable: false`: check the existing encryption-key/previous-key configuration; do not generate replacement keys.
- `counter_ahead_of_acceptance_window: true`: investigate server clock rollback and NTP before any supervised account recovery.
- A positive `seconds_until_unused_time_step` can be normal immediately after a successful code was consumed; wait for that interval and a fresh code.
- If NTP is synchronized, the phone uses automatic date/time, the key is readable and the counter is not ahead, check that the phone's GNK ALGO entry matches this account and uses time-based SHA-1, 6 digits, 30 seconds. Readability alone cannot prove the phone has the same key. Recovery requires verified account ownership; do not disable MFA or reset counters based only on a 401.

Source updates improve error messages, prevent duplicate submission, normalize grouped-code paste, show already-enrolled state and serialize verification against the latest database counter. They do not establish the live root cause until these diagnostics are available. See `TROUBLESHOOTING.md` in the source for deployment and test details.
