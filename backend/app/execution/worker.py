"""Read-only periodic reconciliation. Never submits, replaces or retries orders."""
import time,uuid
from sqlalchemy import select
from app.core.config import now
from app.database.session import DB,engine
from app.database.tenancy import set_context
from app.database.readiness import check_schema
from app.models.identity import User
from app.models.trading import BrokerAccount
from app.execution.models import LiveOrder
from app.execution import live_service as live
from app.execution.upstox import ExecutionError
from app.security.authentication import cache

def run_once():
    # Users are global identity rows; each account query uses an explicit tenant.
    with DB() as s:uids=list(s.scalars(select(User.id)))
    for uid in uids:
        with DB() as s:
            set_context(s,uid)
            account_ids=list(s.scalars(select(LiveOrder.account_id).where(LiveOrder.user_id==uid,LiveOrder.status.notin_(live.TERMINAL)).distinct()))
        for account_id in account_ids:
            with DB() as s:
                set_context(s,uid)
                a=s.scalar(select(BrokerAccount).where(BrokerAccount.id==account_id,BrokerAccount.user_id==uid).with_for_update(skip_locked=True))
                if not a:continue
                rows=list(s.scalars(select(LiveOrder).where(LiveOrder.user_id==uid,LiveOrder.account_id==a.id,LiveOrder.status.notin_(live.TERMINAL)).order_by(LiveOrder.created_at).limit(20)))
                try:
                    broker=live.client(s,a);book=broker.book()
                    for row in rows:
                        try:live.reconcile(s,a,row,broker,book)
                        except ExecutionError as error:row.error_code=error.code;row.status='RECONCILE_REQUIRED';row.updated_at=now()
                        cache.set(live.HEARTBEAT,now().isoformat(),ex=45)
                except Exception:
                    for row in rows:row.error_code='RECONCILIATION_UNAVAILABLE';row.updated_at=now()
                s.commit()
            cache.set(live.HEARTBEAT,now().isoformat(),ex=45)

def main():
    from app import main as application
    with engine.connect() as c:check_schema(c)
    while True:
        try:
            cache.set(live.HEARTBEAT,now().isoformat(),ex=45)
            run_once()
        except Exception:print('Execution reconciliation unavailable; no orders submitted by worker.',flush=True)
        time.sleep(10)
if __name__=='__main__':main()
