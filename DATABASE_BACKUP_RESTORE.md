# Backup and recovery

Configure a GPG recipient public key on the operator host and set GNK_BACKUP_RECIPIENT to its reviewed fingerprint. deploy/backup_database.sh streams a custom-format pg_dump directly into GPG encryption, writes no plaintext dump, creates a checksum and avoids overwriting existing backups. The database must already be running. Keep backup private keys off the application VM where possible.

Copy encrypted backups and manifests off-host, define retention and monitor failed jobs. Back up encryption keys separately in a controlled secret store: a DB dump alone cannot recover encrypted broker/MFA fields. No automatic retention deletion is performed by these scripts.

Restore only into a separately provisioned empty database/container with API stopped. Set GNK_RESTORE_CONFIRM=RESTORE_STOPPED_DATABASE, then deploy/restore_database.sh path.dump.gpg. The script requires a matching checksum manifest, decrypts into pg_restore and uses a single transaction with exit-on-error. It does not drop or clean existing tables; populated targets fail safely. There is no claim that it verifies an empty target before restore; conflicts cause rollback.

Perform restoration drills on an isolated host, validate schema/record counts and application behavior, then plan a reviewed cutover. Do not test restore against the live database. Restore drills have not been executed here. Downgrade 0002 is intentionally blocked; design a forward fix or perform a reviewed backup restoration.
