from app.database.session import DB
from app.models.trading import BrokerIntegration, BrokerAccount, BrokerCredential
from app.core.config import expired
from sqlalchemy import select, func
with DB() as s:
    for broker in ['dhan', 'zerodha', 'upstox', 'angelone', 'fyers', '5paisa', 'icici']:
        config = s.get(BrokerIntegration, broker)
        count = s.scalar(select(func.count(BrokerAccount.id)).where(BrokerAccount.broker == broker))
        print(broker, 'auth-reviewed' if config and config.auth_verified else 'disabled', 'visible_accounts=' + str(count), 'live=blocked')
print('Counts are subject to the current database role/RLS. This is not a live broker connectivity test.')
