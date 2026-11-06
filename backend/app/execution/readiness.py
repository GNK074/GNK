"""Read-only account activation checks. Never approves, arms or sends orders."""
from sqlalchemy import select
from app.core.config import settings,expired
from app.models.trading import BrokerAccount,BrokerCredential,Strategy,PlatformControl,RiskConfiguration
from app.execution.models import LiveOrder
from app.security.encryption import open_credentials
from . import live_service as live

def check(code,title,passed,action,owner):
    return dict(code=code,title=title,passed=bool(passed),action=action,owner=owner)

def snapshot(s,uid,broker):
    server=live.enabled(broker) if broker=='dhan' else live.enabled()
    approved=live.broker_approved(s,broker) if broker=='dhan' else live.broker_approved(s)
    worker=live.worker_ready()
    flags=['TRADING_ENABLED','LIVE_TRADING_ENABLED',broker.upper()+'_EXECUTION_ENABLED']
    disabled=[name for name in flags if not getattr(settings,name.lower())]
    platform=s.get(PlatformControl,'global')
    risk=s.scalar(select(RiskConfiguration).where(RiskConfiguration.user_id==uid))
    strategy=bool(s.scalar(select(Strategy.id).where(Strategy.user_id==uid,Strategy.approved.is_(True)).limit(1)))
    checks=[
        check('SERVER_ACTIVATION','Server live placement',server,'Operator: configure '+', '.join(disabled or flags)+' and the broker-specific review tracking reference, tick multiplier and registered egress IP.','operator'),
        check('BROKER_APPROVAL','Broker production approval',approved,'Super administrator: complete the existing broker evidence review and production approval.','super_admin'),
        check('RECONCILIATION_WORKER','Execution reconciliation worker',worker,'Operator: restore the execution-worker service and Redis heartbeat.','operator'),
        check('PLATFORM_STOP','Platform emergency stop cleared',platform and not platform.kill_switch,'Super administrator: review and clear the platform emergency stop in Administration.','super_admin'),
        check('PERSONAL_STOP','Personal emergency stop cleared',not risk or not risk.kill_switch,'Account owner: review personal risk settings and clear the emergency stop.','owner'),
        check('APPROVED_STRATEGY','Approved strategy available',strategy,'Create a strategy and have the super administrator authorize it for live execution.','owner_and_super_admin'),
    ]
    accounts=[]
    for a in s.scalars(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.broker==broker)):
        credential=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==a.id))
        credential_ready=False
        if credential and credential.expires_at and not expired(credential.expires_at):
            try:
                data=open_credentials(uid,a.id,credential.ciphertext)
                token=data.get('credentials',{}).get('access_token')
                credential_ready=data.get('connection_method')=='individual_credentials' and isinstance(token,str) and bool(token)
            except Exception:pass
        uncertain=bool(s.scalar(select(LiveOrder.id).where(LiveOrder.user_id==uid,LiveOrder.account_id==a.id,LiveOrder.status.in_(live.UNCERTAIN)).limit(1)))
        account_checks=[
            check('BROKER_CONNECTION','Verified broker connection',a.status=='connected','Reconnect your own broker account in Brokers & exchanges.','owner'),
            check('BROKER_SESSION','Current execution credentials',credential_ready,'Reconnect or renew your verified individual broker session.','owner'),
            check('ACCOUNT_AUTHORIZATION','Account authorized for live execution',a.live_authorized,'Super administrator: authorize this owned broker account and its strategy in Administration.','super_admin'),
            check('ACCOUNT_ARMED','Account armed by owner',not a.kill_switch,'Account owner: type ENABLE LIVE '+broker.upper()+' and select Arm account.','owner'),
            check('UNCERTAIN_ORDERS','Uncertain order reconciliation complete',not uncertain,'Reconcile existing UNKNOWN or RECONCILE_REQUIRED orders before submitting another.','owner'),
        ]
        blockers=[c for c in checks+account_checks if not c['passed']]
        accounts.append(dict(id=a.id,broker=a.broker,status=a.status,live_authorized=a.live_authorized,armed=not a.kill_switch,checks=account_checks,blockers=blockers,placement_ready=not blockers))
    blockers=[c for c in checks if not c['passed']]
    if not accounts:blockers.append(check('BROKER_ACCOUNT','Broker account connected',False,'Connect your own '+broker.title()+' account in Brokers & exchanges.','owner'))
    return dict(broker=broker,server_enabled=bool(server),broker_approved=bool(approved),reconciliation_healthy=bool(worker),scope='NSE EQ intraday LIMIT DAY; no short selling',checks=checks,blockers=blockers,accounts=accounts,placement_ready=any(a['placement_ready'] for a in accounts),order_checks='Each submission still verifies instrument scope, fresh quotes, price/tick alignment, current risk and broker identity. This readiness read never sends an order.')
