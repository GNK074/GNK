"""Guarded NSE equity intraday LIMIT execution; no automatic order retries."""
import json,uuid
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select,func
from fastapi import HTTPException
from app.core.config import settings,now,digest,expired
from app.models.identity import User
from app.models.trading import BrokerAccount,BrokerCredential,Strategy,ProductionStatus,PlatformControl
from app.execution.models import LiveOrder
from app.execution.upstox import UpstoxExecution,ExecutionError,decimal,integer
from app.execution.routes import risk_for
from app.security.encryption import open_credentials
from app.security.authentication import cache
from app.security.ownership import owned
from app.services.accounts import audit
from app.brokers.approval.approval_service import missing_requirements
from app.market_data.models import MarketInstrument
from app.market_data.service import MarketDataService
TERMINAL={'FILLED','CANCELLED','REJECTED'}
UNCERTAIN={'SUBMITTING','UNKNOWN','RECONCILE_REQUIRED'}
HEARTBEAT='gnk:execution:heartbeat'
def fail(message):raise HTTPException(409,message)
def enabled(broker='upstox'):return settings.trading_enabled and settings.live_trading_enabled and (settings.dhan_execution_enabled if broker=='dhan' else settings.upstox_execution_enabled if broker=='upstox' else False)

def worker_ready():
    try:return bool(cache.exists(HEARTBEAT))
    except Exception:return False

def broker_approved(s,broker='upstox'):
    status=s.get(ProductionStatus,broker)
    return bool(status and status.approved and not missing_requirements(s,broker))

def client(s,account):
    if account.broker not in ('upstox','dhan'):fail('This broker execution adapter is not implemented')
    if account.status!='connected' or not account.account_identifier:fail('Reconnect and verify your broker account')
    credential=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==account.id,BrokerCredential.user_id==account.user_id))
    if not credential or not credential.expires_at or expired(credential.expires_at):fail('Trading credentials are missing or expired')
    try:
        data=open_credentials(account.user_id,account.id,credential.ciphertext)
        if data.get('connection_method')!='individual_credentials':raise ValueError()
        token=data['credentials']['access_token']
        if not isinstance(token,str) or not token:raise ValueError()
    except Exception:fail('Reconnect using verified individual broker trading credentials')
    if account.broker=='dhan':
        from app.brokers.dhan.execution import DhanExecution
        from app.portfolio.service import version
        return DhanExecution(account.account_identifier,token,account.id,account.user_id,credential_version=version(credential))
    return UpstoxExecution(token,account.id)

def gates(s,account,strategy=None):
    if not (enabled(account.broker) if account.broker=='dhan' else enabled()):fail('Live execution is disabled by server configuration')
    if not (broker_approved(s,account.broker) if account.broker=='dhan' else broker_approved(s)):fail('Broker production approval is missing, revoked or expired')
    if not worker_ready():fail('Execution reconciliation worker is unavailable')
    if not account.live_authorized or account.kill_switch:fail('Live execution is not armed for this broker account')
    if strategy and not strategy.approved:fail('Strategy is not approved for live execution')
    platform=s.scalar(select(PlatformControl).where(PlatformControl.id=='global').with_for_update())
    if not platform or platform.kill_switch:fail('Platform emergency stop is active')
    risk=risk_for(s,account.user_id)
    if risk.kill_switch:fail('Personal emergency stop is active')
    return risk

def quote_for(s,uid,account,instrument):
    if account.broker!='dhan':return MarketDataService(s,uid).require_live_quote(instrument.instrument_key)
    from app.brokers.dhan import streams
    credential=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==account.id))
    from app.portfolio.service import version
    try:tick=streams.latest(uid,account.id,version(credential),instrument.instrument_key)
    except Exception:fail('Private Dhan quote service is unavailable')
    if tick.get('data_status')!='LIVE':fail('Subscribe to a fresh private Dhan quote before live placement')
    return tick

def public(row):
    return {k:getattr(row,k) for k in ('id','account_id','strategy_id','instrument_key','symbol','side','quantity','price','product','status','provider_order_id','filled_quantity','average_price','fills','error_code','created_at','updated_at','reconciled_at')}

def validate_risk(s,uid,risk,data,instrument,positions,book):
    # All broker positions and pending orders count, including manual/external activity.
    if any(not isinstance(p,dict) for p in positions) or any(not isinstance(o,dict) for o in book):raise ExecutionError('INVALID_ACCOUNT_SNAPSHOT')
    if data.quantity>risk.max_quantity or data.price*data.quantity>risk.max_order_value:fail('Order exceeds quantity or notional risk limit')
    local=now().astimezone(ZoneInfo('Asia/Kolkata'));midnight=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    count=s.scalar(select(func.count()).select_from(LiveOrder).where(LiveOrder.user_id==uid,LiveOrder.created_at>=midnight))
    if max(count,len(book))>=risk.max_daily_orders:fail('Daily live order limit reached')
    loss=sum((decimal(p.get('realised'))+decimal(p.get('unrealised')) for p in positions),Decimal(0))
    if -loss>=risk.max_daily_loss:fail('Broker account loss limit reached')
    net=0;active=set();pending_buy=0;pending_sell=0;exposure=Decimal(0)
    for p in positions:
        qty=integer(p.get('quantity'))
        if qty:
            active.add(p.get('instrument_token'));exposure+=abs(qty*decimal(p.get('last_price')))
        if p.get('instrument_token')==instrument.instrument_key and p.get('product')=='I':net+=qty
    for o in book:
        status=str(o.get('status','')).lower()
        if status in ('complete','cancelled','rejected'):continue
        if not status:raise ExecutionError('UNKNOWN_BROKER_ORDER_STATUS')
        remaining=integer(o.get('quantity'))-integer(o.get('filled_quantity'))
        if remaining<0:raise ExecutionError('INVALID_BROKER_QUANTITY')
        if remaining:
            if o.get('transaction_type') not in ('BUY','SELL'):raise ExecutionError('UNKNOWN_BROKER_SIDE')
            active.add(o.get('instrument_token'))
            open_price=decimal(o.get('price'))
            if open_price<=0:fail('An unpriced external order prevents reliable exposure checks')
            exposure+=remaining*open_price
            if o.get('instrument_token')==instrument.instrument_key and o.get('product')=='I':
                if o['transaction_type']=='BUY':pending_buy+=remaining
                else:pending_sell+=remaining
    if net<0:fail('Existing short exposure requires broker-side review')
    if data.side=='SELL' and data.quantity>net-pending_sell:fail('Insufficient unreserved intraday long quantity; short selling is not supported')
    if data.side=='BUY':
        if net+pending_buy+data.quantity>risk.max_quantity:fail('Projected instrument quantity exceeds risk limit')
        if (net+pending_buy+data.quantity)*data.price>risk.max_order_value:fail('Projected instrument exposure exceeds risk limit')
        active.add(instrument.instrument_key)
        if len(active)>risk.max_positions:fail('Position limit reached')
        if exposure+data.price*data.quantity>risk.max_order_value*risk.max_positions:fail('Portfolio exposure limit reached')

def submit(s,u,data):
    # Ownership checks precede global activation information, preventing ID probing.
    s.scalar(select(User).where(User.id==u.id).with_for_update())
    account=owned(s,BrokerAccount,data.broker_account_id,u.id,lock=True)
    strategy=owned(s,Strategy,data.strategy_id,u.id)
    fingerprint=digest(json.dumps(data.model_dump(mode='json'),sort_keys=True))
    old=s.scalar(select(LiveOrder).where(LiveOrder.user_id==u.id,LiveOrder.idempotency_key==data.idempotency_key))
    if old:
        if old.request_hash!=fingerprint:fail('Idempotency key belongs to a different live order')
        return old
    risk=gates(s,account,strategy)
    if account.broker=='dhan':
        clock=now().astimezone(ZoneInfo('Asia/Kolkata'))
        if clock.weekday()>4 or not (9,15)<=(clock.hour,clock.minute)<(15,20):fail('Dhan intraday entry window is 09:15–15:20 IST on trading weekdays; fresh exchange ticks are also required')
    if not data.confirm_real_money:fail('Explicit real-money order confirmation is required')
    if not data.instrument_id:fail('Choose an instrument from the synchronized master')
    instrument=s.get(MarketInstrument,data.instrument_id)
    if not instrument or instrument.status!='ACTIVE' or instrument.segment!='NSE_EQ' or instrument.instrument_type!='EQ':fail('Live execution currently supports active NSE EQ instruments only')
    synced=instrument.synced_at if instrument.synced_at.tzinfo else instrument.synced_at.replace(tzinfo=timezone.utc)
    if now()-synced>timedelta(hours=24):fail('Refresh the stale instrument master before live placement')
    if instrument.lot_size!=1:fail('This release supports unit-lot NSE equity only')
    if data.symbol!=instrument.symbol:fail('Symbol does not match the selected instrument')
    if instrument.provider!=account.broker:fail('Instrument provider does not match this broker account')
    tick=quote_for(s,u.id,account,instrument)
    ltp=decimal(tick['ltp'])
    if ltp<=0 or abs(data.price-ltp)*100>ltp*settings.live_price_deviation_percent:fail('Limit price is outside the configured band around the fresh quote')
    step=decimal(instrument.tick_size)*(settings.dhan_tick_size_multiplier if account.broker=='dhan' else settings.live_tick_size_multiplier)
    if step<=0 or data.price%step:fail('Price is not aligned to the verified instrument tick size')
    uncertain=s.scalar(select(LiveOrder.id).where(LiveOrder.account_id==account.id,LiveOrder.user_id==u.id,LiveOrder.status.in_(UNCERTAIN)).limit(1))
    if uncertain:fail('Resolve the account\'s uncertain order before submitting another')
    broker=client(s,account);broker.verify_identity(account.account_identifier)
    book=broker.book();positions=broker.positions();validate_risk(s,u.id,risk,data,instrument,positions,book)
    row=LiveOrder(user_id=u.id,account_id=account.id,strategy_id=strategy.id,instrument_id=instrument.id,instrument_key=instrument.instrument_key,symbol=instrument.symbol,side=data.side,quantity=data.quantity,price=data.price,tag='GNK'+(uuid.uuid4().hex[:24] if account.broker=='dhan' else uuid.uuid4().hex),idempotency_key=data.idempotency_key,request_hash=fingerprint)
    s.add(row);s.flush()
    from app.trade_details.models import TradeSignal
    s.add(TradeSignal(user_id=u.id,strategy_id=strategy.id,account_id=account.id,instrument_id=instrument.id,symbol=instrument.symbol,strike_price=instrument.strike,order_type='LIMIT',side=data.side,quantity=data.quantity,reference_price=data.price,signal_time=row.created_at,source='ORDER_REQUEST',source_order_id=row.id,note='User-submitted order request; this signal is not a broker fill.'))
    audit(s,u.id,'live_intent_created:'+row.id);s.commit()
    # The durable SUBMITTING intent survives crash/timeout. It is never resent.
    account_id=account.id;strategy_id=strategy.id;order_id=row.id
    uid=u.id
    s.expire_all()
    s.scalar(select(User).where(User.id==uid).with_for_update())
    account=owned(s,BrokerAccount,account_id,u.id,lock=True)
    strategy=owned(s,Strategy,strategy_id,u.id)
    row=s.get(LiveOrder,order_id)
    try:
        current_user=s.get(User,u.id)
        if not current_user.active or not current_user.verified:fail('Account access was revoked before submission')
        gates(s,account,strategy)
        broker=client(s,account)
        fresh=quote_for(s,u.id,account,instrument)
        if abs(data.price-decimal(fresh['ltp']))*100>decimal(fresh['ltp'])*settings.live_price_deviation_percent:fail('Quote moved outside price band before submission')
        row.provider_order_id=broker.place(row);row.status='PENDING'
    except ExecutionError as error:
        row.status='UNKNOWN' if error.ambiguous else 'REJECTED';row.error_code=error.code
    except HTTPException:
        row.status='REJECTED';row.error_code='ACTIVATION_REVOKED_BEFORE_SEND'
    except Exception:
        row.status='UNKNOWN';row.error_code='SUBMISSION_REQUIRES_RECONCILIATION'
    row.updated_at=now();audit(s,u.id,'live_submission:'+row.id+':'+row.status);s.commit();return row

def reconcile(s,account,row,broker=None,book=None):
    broker=broker or client(s,account)
    broker.verify_identity(account.account_identifier)
    book=broker.book() if book is None else book
    matches=[o for o in book if isinstance(o,dict) and ((row.provider_order_id and o.get('order_id')==row.provider_order_id) or o.get('tag')==row.tag)]
    if len(matches)!=1:
        row.error_code='ORDER_NOT_FOUND_OR_AMBIGUOUS';row.status=row.status if row.status in TERMINAL else 'RECONCILE_REQUIRED';row.updated_at=now();return row
    item=matches[0]
    if item.get('instrument_token')!=row.instrument_key or item.get('transaction_type')!=row.side or integer(item.get('quantity'))!=row.quantity or decimal(item.get('price'))!=row.price or item.get('product')!='I' or item.get('order_type')!='LIMIT' or item.get('tag')!=row.tag:
        raise ExecutionError('BROKER_ORDER_IDENTITY_MISMATCH')
    order_id=item.get('order_id')
    if not isinstance(order_id,str) or not 1<=len(order_id)<=100:raise ExecutionError('INVALID_BROKER_ORDER_ID')
    if row.provider_order_id and row.provider_order_id!=order_id:raise ExecutionError('BROKER_ORDER_IDENTITY_MISMATCH')
    filled=integer(item.get('filled_quantity'))
    if not row.filled_quantity<=filled<=row.quantity:raise ExecutionError('BROKER_FILL_REGRESSION')
    fills=[];seen=set()
    if filled:
        for trade in broker.trades(order_id):
            if not isinstance(trade,dict) or trade.get('order_id')!=order_id or trade.get('transaction_type')!=row.side or trade.get('product')!='I':raise ExecutionError('BROKER_TRADE_IDENTITY_MISMATCH')
            tid=trade.get('trade_id');qty=integer(trade.get('quantity'));price=decimal(trade.get('average_price'))
            if not isinstance(tid,str) or not tid or qty<=0 or price<=0:raise ExecutionError('INVALID_BROKER_TRADE')
            if tid in seen:raise ExecutionError('DUPLICATE_BROKER_TRADE')
            seen.add(tid);fills.append({'trade_id':tid,'quantity':qty,'price':str(price),'exchange_timestamp':str(trade.get('exchange_timestamp',''))[:100]})
        if sum(t['quantity'] for t in fills)!=filled:raise ExecutionError('BROKER_FILLS_NOT_RECONCILED')
    status=str(item.get('status','')).lower()
    mapped={'complete':'FILLED','cancelled':'CANCELLED','rejected':'REJECTED','open':'OPEN','open pending':'PENDING','validation pending':'PENDING','put order req received':'PENDING','trigger pending':'PENDING','cancel pending':'CANCEL_PENDING','modify pending':'PENDING'}.get(status,'RECONCILE_REQUIRED')
    if mapped=='FILLED' and filled!=row.quantity:raise ExecutionError('BROKER_FILLS_NOT_RECONCILED')
    if row.status in TERMINAL and mapped!=row.status:raise ExecutionError('BROKER_TERMINAL_STATE_REGRESSION')
    row.provider_order_id=order_id;row.status=mapped;row.filled_quantity=filled;row.fills=fills
    row.average_price=sum((decimal(t['price'])*t['quantity'] for t in fills),Decimal(0))/filled if filled else None
    row.error_code=None if mapped!='RECONCILE_REQUIRED' else 'UNKNOWN_BROKER_ORDER_STATUS';row.reconciled_at=now();row.updated_at=now();return row
