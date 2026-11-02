"""Operator-only, read-only MFA diagnosis. Never returns identifiers or secrets."""
import base64
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.identity import User
from app.security.encryption import decrypt

def diagnose_mfa(session, email, timestamp=None):
    stamp = datetime.now(timezone.utc).timestamp() if timestamp is None else timestamp
    result = {'server_utc': datetime.fromtimestamp(stamp, timezone.utc).isoformat()}
    row = session.execute(select(User.mfa_enabled, User.mfa_counter, User.mfa_secret).where(User.email == email.strip().lower())).first()
    result['account_found'] = row is not None
    if row is None:
        return result
    enabled, counter, encrypted = row
    result['mfa_enabled'] = enabled
    result['setup_key_present'] = bool(encrypted)
    result['setup_key_readable'] = False
    if encrypted:
        try:
            secret = decrypt(encrypted)
            key = base64.b32decode(secret + '=' * ((8-len(secret)%8)%8))
            result['setup_key_readable'] = len(key) >= 16
        except Exception:
            pass
    current = int(stamp // 30)
    result['accepted_code_recorded'] = counter >= 0
    result['counter_ahead_of_acceptance_window'] = counter > current + 1
    result['seconds_until_unused_time_step'] = max(0, (counter+1)*30-int(stamp)) if counter >= 0 else 0
    if not enabled:
        result['next_step'] = 'MFA is not enabled for this account. Inspect the login response and use the existing authenticated enrollment flow.'
    elif result['counter_ahead_of_acceptance_window']:
        result['next_step'] = 'Investigate server clock changes and NTP synchronization. Do not reset the replay counter to bypass verification.'
    elif not result['setup_key_readable']:
        result['next_step'] = 'Check existing encryption-key configuration and previous keys; do not generate replacement keys.'
    else:
        result['next_step'] = 'Check server NTP and phone automatic date/time, then use the GNK ALGO authenticator entry for this account. If it still fails, use a verified operator-assisted recovery process.'
    return result
