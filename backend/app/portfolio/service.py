"""Owner-scoped portfolio queries and idempotent snapshot synchronization."""
from datetime import timedelta,timezone
from decimal import Decimal
import hashlib,uuid,json
from sqlalchemy import select
from fastapi import HTTPException
from app.core.config import now,expired
from app.database.session import DB
from app.database.tenancy import set_context
from app.models.trading import BrokerAccount,BrokerCredential
from app.security.authentication import cache
from app.security.encryption import open_credentials
from .models import PortfolioSnapshot,PortfolioSync
from .adapters import ADAPTERS,KINDS,PortfolioError,number
STALE_SECONDS=180
REFRESH_SECONDS=30
SYNC_SECONDS=60
HEARTBEAT='gnk:portfolio:heartbeat'

def safe_failure_code(error):
    from sqlalchemy.exc import IntegrityError,SQLAlchemyError
    from redis.exceptions import RedisError
    if isinstance(error,IntegrityError):return 'DATABASE_INTEGRITY_ERROR'
    if isinstance(error,SQLAlchemyError):return 'DATABASE_OPERATION_FAILED'
    if isinstance(error,RedisError):return 'CACHE_UNAVAILABLE'
    return 'INTERNAL_SYNC_ERROR'

def utc(d):return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d
def version(c):return hashlib.sha256(c.ciphertext.encode()).hexdigest()
def serialized(v):
    if isinstance(v,Decimal):return str(v)
    if isinstance(v,list):return [serialized(x) for x in v]
    if isinstance(v,dict):return {k:serialized(x) for k,x in v.items()}
    return v

def owned_accounts(s,uid,account_id=None,broker=None):
    query=select(BrokerAccount).where(BrokerAccount.user_id==uid)
    if account_id:query=query.where(BrokerAccount.id==account_id)
    if broker:query=query.where(BrokerAccount.broker==broker)
    return list(s.scalars(query.order_by(BrokerAccount.created_at)))

def account_data(s,uid,account_id=None,broker=None):
    result=[]
    for a in owned_accounts(s,uid,account_id,broker):
        c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==a.id))
        sync=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==a.id))
        snaps=list(s.scalars(select(PortfolioSnapshot).where(PortfolioSnapshot.user_id==uid,PortfolioSnapshot.account_id==a.id)))
        valid=[v for v in snaps if not c or v.credential_version==version(c)]
        state='CONNECTED'
        if a.broker not in ADAPTERS:state='UNSUPPORTED'
        elif a.status!='connected' or not c:state='DISCONNECTED'
        elif c.expires_at is None or expired(c.expires_at):state='SESSION_EXPIRED'
        elif sync and sync.state=='SESSION_EXPIRED':state='SESSION_EXPIRED'
        elif sync and sync.state=='SYNCING' and sync.attempted_at and (now()-utc(sync.attempted_at)).total_seconds()<300:state='SYNCING'
        elif not valid:state='ERROR' if sync and sync.errors else 'PENDING'
        elif any((now()-utc(v.fetched_at)).total_seconds()>STALE_SECONDS for v in valid) or len(valid)!=len(KINDS) or (sync and sync.errors):state='STALE'
        stamps=[utc(v.fetched_at) for v in valid]
        result.append(dict(id=a.id,broker=a.broker,account=a.account_identifier,status=state,connection_status=a.status,sync_state=sync.state if sync else 'PENDING',next_attempt_at=sync.next_attempt_at if sync else None,completed_at=sync.completed_at if sync else None,capabilities={k:a.broker in ADAPTERS for k in KINDS},last_success=min(stamps) if len(valid)==len(KINDS) else None,last_attempt=sync.attempted_at if sync else None,errors=sync.errors if sync else {},requested_at=sync.requested_at if sync else None,reauthorize_url='/user/broker-and-exchanges',snapshots={v.kind:v for v in valid}))
    return result

def public_accounts(s,uid,**filters):
    return [{k:v for k,v in a.items() if k!='snapshots'} for a in account_data(s,uid,**filters)]

def connected(s,uid,aid,broker):
    """Queue a newly verified credential in the connection's own transaction.

    Old credentials' errors/backoff must not survive replacement. Ordinary UI
    refreshes still respect backoff. Existing snapshots are retained and remain
    excluded by their credential fingerprint until the new session succeeds.
    """
    if broker not in ADAPTERS:return
    state=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==aid).with_for_update())
    if not state:state=PortfolioSync(user_id=uid,account_id=aid);s.add(state)
    state.state='QUEUED';state.errors={};state.failures=0
    state.requested_at=now();state.next_attempt_at=now()
    state.attempted_at=None;state.completed_at=None

def queue(s,uid,account_id=None):
    accounts=owned_accounts(s,uid,account_id)
    if account_id and not accounts:raise HTTPException(404,'Broker account not found')
    accepted=[];blocked=[]
    for a in accounts:
        if a.broker not in ADAPTERS or a.status!='connected':blocked.append(a.id);continue
        state=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==a.id))
        if state and state.requested_at and (now()-utc(state.requested_at)).total_seconds()<REFRESH_SECONDS:blocked.append(a.id);continue
        if not state:state=PortfolioSync(user_id=uid,account_id=a.id);s.add(state)
        state.requested_at=now()
        # Do not erase broker backoff on user refresh or steal an active sync.
        if state.state!='SYNCING':state.state='QUEUED'
        accepted.append(a.id)
    s.commit()
    return dict(queued=accepted,throttled_or_unavailable=blocked,refresh_after_seconds=REFRESH_SECONDS)

def classify_holdings(s,rows):
    # ISIN prefixes also cover debt; never infer equity solely from INE.
    from app.market_data.models import MarketInstrument
    unknown=[r for r in rows if r.get('isin') and r.get('asset_class')=='UNKNOWN']
    keys={segment+'|'+r['isin'] for r in unknown for segment in ('NSE_EQ','BSE_EQ')}
    verified=set()
    keys=list(keys)
    for offset in range(0,len(keys),500):
        matches=s.scalars(select(MarketInstrument).where(MarketInstrument.instrument_key.in_(keys[offset:offset+500]),MarketInstrument.instrument_type=='EQ',MarketInstrument.status=='ACTIVE'))
        verified.update(m.instrument_key.partition('|')[2] for m in matches)
    for r in unknown:
        if r['isin'] in verified:r['asset_class']='EQUITY';r['classification_source']='INSTRUMENT_MASTER'
    return rows

def build_adapter(a,c):
    data=open_credentials(a.user_id,a.id,c.ciphertext)
    credentials=data.get('credentials',data)
    return ADAPTERS[a.broker](credentials,a.account_identifier)

def sync_account(uid,aid):
    token=uuid.uuid4().hex;key=f'gnk:portfolio:lock:{uid}:{aid}'
    if not cache.set(key,token,nx=True,ex=300):return False
    try:
        with DB() as s:
            set_context(s,uid)
            a=s.scalar(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.id==aid))
            state=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==aid))
            if not a or a.status!='connected' or a.broker not in ADAPTERS:return False
            if state and state.next_attempt_at and utc(state.next_attempt_at)>now():return False
            if not state:state=PortfolioSync(user_id=uid,account_id=aid);s.add(state)
            c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==aid))
            state.attempted_at=now()
            if not c or c.expires_at is None or expired(c.expires_at):
                state.state='SESSION_EXPIRED';state.errors={'session':'SESSION_EXPIRED'};state.next_attempt_at=now()+timedelta(seconds=60);s.commit();return False
            fingerprint=version(c)
            try:adapter=build_adapter(a,c)
            except Exception:
                state.state='ERROR';state.errors={'session':'CREDENTIALS_UNAVAILABLE'};state.next_attempt_at=now()+timedelta(seconds=300);s.commit();return False
            state.state='SYNCING';s.commit()
        errors={};success=0
        for kind in KINDS:
            try:
                payload=serialized(adapter.fetch(kind))
                if not isinstance(payload,list) or (kind=='funds' and not payload):raise PortfolioError('INVALID_RESPONSE')
            except Exception as e:
                errors[kind]=e.code if isinstance(e,PortfolioError) else 'INVALID_RESPONSE'
                if errors[kind] in ('SESSION_EXPIRED','RATE_LIMITED'):break
                continue
            # Fenced lease renewal: another worker cannot publish after this one expires.
            if not cache.eval("if redis.call('GET',KEYS[1])==ARGV[1] then redis.call('EXPIRE',KEYS[1],300); return 1 end return 0",1,key,token):return False
            with DB() as s:
                set_context(s,uid)
                a=s.scalar(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.id==aid).with_for_update())
                c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==aid))
                if not a or a.status!='connected' or not c or version(c)!=fingerprint or c.expires_at is None or expired(c.expires_at):return False
                # Classification queries may autoflush the session. Complete all
                # lookups before adding a snapshot with required value fields.
                if kind=='holdings':payload=classify_holdings(s,payload)
                snap=s.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.user_id==uid,PortfolioSnapshot.account_id==aid,PortfolioSnapshot.kind==kind))
                if not snap:snap=PortfolioSnapshot(user_id=uid,account_id=aid,kind=kind);s.add(snap)
                snap.rows=payload;snap.fetched_at=now();snap.credential_version=fingerprint;s.commit();success+=1
            cache.set(HEARTBEAT,now().isoformat(),ex=180)
        if not cache.eval("if redis.call('GET',KEYS[1])==ARGV[1] then redis.call('EXPIRE',KEYS[1],300); return 1 end return 0",1,key,token):return False
        with DB() as s:
            set_context(s,uid)
            a=s.scalar(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.id==aid).with_for_update())
            c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==aid))
            # An old in-flight failure cannot overwrite a reconnect's new queue.
            if not a or a.status!='connected' or not c or version(c)!=fingerprint or c.expires_at is None or expired(c.expires_at):return False
            state=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==aid))
            if not state:return False
            state.errors=errors;state.completed_at=now();state.failures=state.failures+1 if errors else 0
            state.state='SESSION_EXPIRED' if 'SESSION_EXPIRED' in errors.values() else 'PARTIAL' if errors and success else 'ERROR' if errors else 'CONNECTED'
            state.next_attempt_at=now()+timedelta(seconds=min(900,SYNC_SECONDS*2**min(state.failures,4)))
            s.commit()
            if errors:print('Portfolio sync incomplete. Broker: '+a.broker+' Codes: '+json.dumps(errors,sort_keys=True),flush=True)
        return True
    except Exception as error:
        # Keep unexpected failures visible and bounded instead of retrying every
        # five seconds. Never persist raw exceptions, statements or credentials.
        try:
            if cache.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return 1 end return 0",1,key,token):
                with DB() as s:
                    set_context(s,uid)
                    a=s.scalar(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.id==aid).with_for_update())
                    c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==aid))
                    state=s.scalar(select(PortfolioSync).where(PortfolioSync.user_id==uid,PortfolioSync.account_id==aid).with_for_update())
                    if a and a.status=='connected' and c and version(c)==fingerprint and state and state.state=='SYNCING':
                        state.state='ERROR';state.errors={'sync':safe_failure_code(error)}
                        state.failures+=1;state.completed_at=now()
                        state.next_attempt_at=now()+timedelta(seconds=min(900,SYNC_SECONDS*2**min(state.failures,4)))
                        s.commit()
        except Exception:pass
        raise
    finally:
        cache.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0",1,key,token)

def dataset(s,uid,kind,account_id=None,broker=None,exchange=None,product=None,asset_class=None,q=None):
    accounts=account_data(s,uid,account_id,broker);items=[];coverage=[]
    for a in accounts:
        snap=a['snapshots'].get(kind)
        fresh=bool(snap and a['connection_status']=='connected' and a['status'] not in ('SESSION_EXPIRED','DISCONNECTED') and (now()-utc(snap.fetched_at)).total_seconds()<=STALE_SECONDS and kind not in a['errors'] and 'session' not in a['errors'] and 'sync' not in a['errors'])
        coverage.append(dict(account_id=a['id'],broker=a['broker'],status=a['status'],available=bool(snap),fresh=fresh,fetched_at=snap.fetched_at if snap else None,error=a['errors'].get(kind) or a['errors'].get('session') or a['errors'].get('sync')))
        if not snap:continue
        for row in snap.rows:
            if kind!='funds' and exchange and str(row.get('exchange','')).upper()!=exchange.upper():continue
            if kind!='funds' and product and str(row.get('product','')).upper()!=product.upper():continue
            if kind!='funds' and asset_class and str(row.get('asset_class','')).upper()!=asset_class.upper():continue
            if kind!='funds' and q and q.casefold() not in ' '.join(str(row.get(k,'')) for k in ('symbol','isin','order_id','trade_id')).casefold():continue
            items.append(dict(row,account_id=a['id'],account=a['account'],broker=a['broker'],fetched_at=snap.fetched_at,fresh=fresh,source='BROKER_REPORTED',price_status='BROKER_SNAPSHOT' if fresh else 'STALE_SNAPSHOT'))
    return items,coverage

def exact_sum(rows,key):
    values=[number(r.get(key)) for r in rows]
    return None if any(v is None for v in values) else sum(values,Decimal(0))

def summary(s,uid,**filters):
    h,hc=dataset(s,uid,'holdings',**filters);p,pc=dataset(s,uid,'positions',**filters)
    def metric(data,coverage,key):
        known=[r for r in data if r.get(key) is not None]
        complete=bool(coverage) and all(c['available'] and c['fresh'] for c in coverage) and len(known)==len(data)
        value=exact_sum(data,key) if complete else None
        return dict(value=value,known_subtotal=exact_sum(known,key) if known else None,complete=complete,known_rows=len(known),total_rows=len(data))
    return dict(currency='INR',holdings_invested=metric(h,hc,'invested_value'),holdings_current=metric(h,hc,'current_value'),holdings_pnl=metric(h,hc,'pnl'),positions_realized=metric(p,pc,'realized_pnl'),positions_unrealized=metric(p,pc,'unrealized_pnl'),accounts=public_accounts(s,uid,account_id=filters.get('account_id'),broker=filters.get('broker')),coverage={'holdings':hc,'positions':pc},definition='Holdings and position P&L are separate broker snapshots and must not be added as net worth. Funds are shown per broker ledger, not summed.')

def consolidate(items,kind):
    groups={}
    for r in items:
        # Only verified equity ISIN holdings merge across brokers. No symbol inference.
        key=('ISIN',r['isin'],r['asset_class'],r['currency']) if kind=='holdings' and r.get('isin') and r.get('asset_class')=='EQUITY' and r.get('product') in ('DELIVERY','CNC','D','HLD') else ('ROW',r['account_id'],r['row_key'])
        groups.setdefault(key,[]).append(r)
    result=[]
    for group in groups.values():
        if len(group)==1:result.append(dict(group[0],components=group));continue
        first=group[0];qty=exact_sum(group,'quantity');invested=exact_sum(group,'invested_value');current=exact_sum(group,'current_value');pnl=exact_sum(group,'pnl')
        result.append(dict(first,broker='Multiple',account='Multiple',exchange='Multiple',account_id=None,valuation_basis='SUM_OF_ACCOUNT_SNAPSHOTS',quantity=qty,invested_value=invested,current_value=current,pnl=pnl,average_cost=invested/qty if invested is not None and qty else None,current_price=current/qty if current is not None and qty else None,pnl_percent=pnl/invested*100 if pnl is not None and invested else None,fresh=all(x['fresh'] for x in group),price_status='BROKER_SNAPSHOT' if all(x['fresh'] for x in group) else 'STALE_SNAPSHOT',fetched_at=min(utc(x['fetched_at']) for x in group),components=group))
    return result
