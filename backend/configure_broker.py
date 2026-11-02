"""Operator-reviewed authentication registration, not production trading approval."""
import argparse, getpass, os
from urllib.parse import urlsplit
from app.core.config import settings
from app.database.session import DB
from app.models.trading import BrokerIntegration
from app.security.encryption import encrypt
from app.services.accounts import audit
p = argparse.ArgumentParser()
p.add_argument('--broker', choices=['upstox'], required=True)
p.add_argument('--mode', choices=['PLATFORM', 'INDIVIDUAL', 'HYBRID'], required=True)
p.add_argument('--auth-reviewed', action='store_true')
p.add_argument('--evidence-reference', required=True)
args = p.parse_args()
if not args.auth_reviewed or not args.evidence_reference.startswith('https://'):
    raise SystemExit('Official auth/application review and HTTPS evidence reference are required.')
cid = ''
secret = ''
if args.mode != 'INDIVIDUAL':
    cid = os.getenv('UPSTOX_CLIENT_ID') or input('Upstox application client ID: ').strip()
    secret = os.getenv('UPSTOX_CLIENT_SECRET') or getpass.getpass('Upstox application client secret: ')
redirect = os.getenv('UPSTOX_REDIRECT_URI') or settings.backend_url + '/api/v1/brokers/upstox/callback'
expected = settings.backend_url.rstrip('/') + '/api/v1/brokers/upstox/callback'
if redirect != expected or urlsplit(redirect).scheme != 'https':
    raise SystemExit('Exact HTTPS callback must match BACKEND_URL and registered broker application.')
if args.mode != 'INDIVIDUAL' and (not cid or not secret):
    raise SystemExit('Application credentials required; no changes made.')
with DB() as s:
    item = s.get(BrokerIntegration, args.broker)
    if item:
        raise SystemExit('Integration already exists. Review and rotate it through a dedicated migration; no credentials overwritten.')
    s.add(BrokerIntegration(broker=args.broker, mode=args.mode, auth_verified=True, client_id=cid, encrypted_client_secret=encrypt(secret) if secret else '', redirect_uri=redirect))
    audit(s, None, 'operator_auth_registration:upstox')
    s.commit()
print('Authentication registration saved. Production/live trading approval remains blocked.')
