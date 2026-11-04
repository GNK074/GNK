"""Periodic read-only snapshot worker. Explicit tenant context per account."""
import time
from sqlalchemy import select
from app.core.config import now
from app.database.session import DB,engine
from app.database.tenancy import set_context
from app.database.readiness import check_schema
from app.models.identity import User
from app.models.trading import BrokerAccount
from app.security.authentication import cache
from .service import sync_account,HEARTBEAT,safe_failure_code
from .adapters import ADAPTERS

def run_once():
    with DB() as s:uids=list(s.scalars(select(User.id).where(User.active.is_(True),User.verified.is_(True))))
    for uid in uids:
        with DB() as s:
            set_context(s,uid)
            accounts=list(s.scalars(select(BrokerAccount.id).where(BrokerAccount.user_id==uid,BrokerAccount.status=='connected',BrokerAccount.broker.in_(ADAPTERS))))
        for aid in accounts:
            try:sync_account(uid,aid)
            except Exception as error:print('Portfolio account synchronization unavailable; previous snapshots retained. Code: '+safe_failure_code(error),flush=True)
            cache.set(HEARTBEAT,now().isoformat(),ex=180)

def main():
    from app import main as application
    with engine.connect() as c:check_schema(c)
    while True:
        try:
            cache.set(HEARTBEAT,now().isoformat(),ex=180);run_once()
        except Exception:print('Portfolio worker unavailable; retrying.',flush=True)
        time.sleep(5)
if __name__=='__main__':main()
