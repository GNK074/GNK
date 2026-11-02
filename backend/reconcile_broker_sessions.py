from sqlalchemy import select
from app.database.session import DB
from app.models.trading import BrokerAccount, BrokerCredential
from app.core.config import expired
from app.services.accounts import audit
count = 0
with DB() as s:
    for credential in s.scalars(select(BrokerCredential)):
        if credential.expires_at and expired(credential.expires_at):
            account = s.get(BrokerAccount, credential.account_id)
            if account.status == 'connected':
                account.status = 'expired'
                account.kill_switch = True
                account.live_authorized = False
                audit(s, account.user_id, 'broker_session_expired')
                count += 1
    s.commit()
print('Expired connections marked:', count)
print('This maintenance command does not refresh, revoke or validate provider sessions. RLS restricts its visible rows.')
