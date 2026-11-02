"""Run using reviewed maintenance credentials after an encrypted DB backup."""
import argparse
from sqlalchemy import select
from app.core.config import settings
from app.database.session import DB
from app.models.identity import User
from app.models.trading import BrokerCredential, BrokerIntegration
from app.security.encryption import cipher
from app.services.accounts import audit
p = argparse.ArgumentParser()
p.add_argument('--apply', action='store_true')
args = p.parse_args()
if not args.apply:
    raise SystemExit('Rotation requires --apply. Configure the new primary and previous decrypt keys first; back up the database.')
count = 0
with DB() as s:
    for credential in s.scalars(select(BrokerCredential)):
        credential.ciphertext = cipher().rotate(credential.ciphertext.encode()).decode()
        credential.key_version = settings.encryption_key_version
        count += 1
    for app in s.scalars(select(BrokerIntegration)):
        if app.encrypted_client_secret:
            app.encrypted_client_secret = cipher().rotate(app.encrypted_client_secret.encode()).decode()
            count += 1
    for user in s.scalars(select(User)):
        if user.mfa_secret:
            user.mfa_secret = cipher().rotate(user.mfa_secret.encode()).decode()
            count += 1
    audit(s, None, 'field_key_rotation')
    s.commit()
print('Rotation committed; encrypted fields processed:', count)
