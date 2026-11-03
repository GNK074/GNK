"""Read-only, owner-scoped reporting for actual live orders and reconciled fills."""
import json
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from app.models.trading import BrokerAccount,Strategy
from app.execution.models import LiveOrder
from app.market_data.models import MarketInstrument
from app.market_data.subscription_manager import entitlement,provider_status
from app.market_data.config import market_settings as cfg
from app.market_data.service import get_store
from app.market_data.market_calendar import quality,market_session
from .accounting import accounting,utc
MAX_LEDGER=10000
GROUPS={'OPEN':'ACTIVE','PENDING':'PENDING','SUBMITTING':'PENDING','CANCEL_PENDING':'PENDING','UNKNOWN':'PENDING','RECONCILE_REQUIRED':'PENDING','FILLED':'CLOSED','CANCELLED':'CLOSED','REJECTED':'FAILED'}


def ledger(s,uid):
    rows=list(s.scalars(select(LiveOrder).where(LiveOrder.user_id==uid).order_by(LiveOrder.created_at,LiveOrder.id).limit(MAX_LEDGER+1)))
    if len(rows)>MAX_LEDGER:raise HTTPException(413,'Reporting supports up to 10,000 recorded live orders per account owner; use an operator-reviewed archive for larger ledgers.')
    return rows

def metadata(s,uid):
    accounts={a.id:a for a in s.scalars(select(BrokerAccount).where(BrokerAccount.user_id==uid))}
    strategies={x.id:x for x in s.scalars(select(Strategy).where(Strategy.user_id==uid))}
    return accounts,strategies

def cached_prices(s,uid,orders,instruments):
    # Read cached prices only. Reports never trigger broker requests or orders.
    try:
        access=entitlement(s,uid,'ltpc');allowed=set(access.segments)&cfg.segments
        keys=sorted({o.instrument_key for o in orders if o.instrument_id in instruments and instruments[o.instrument_id].segment in allowed})
        if not keys:return {}
        store=get_store();state=store.state();provider=provider_status(s)
        values=store.client.mget([store.tick_key(k) for k in keys]);result={}
        connected=cfg.upstox_enabled and provider.enabled and state.get('state')=='CONNECTED'
        by_key={x.instrument_key:x for x in instruments.values()}
        for key,raw in zip(keys,values):
            if not raw:continue
            tick=json.loads(raw)
            instrument=by_key.get(key)
            if not instrument:continue
            result[key]=quality(tick,connected,market_session(instrument.segment,{'segments':state.get('segments',{}),'received_at':state.get('updated_at')}))
        return result
    except Exception:return {}

def projections(s,user):
    orders=ledger(s,user.id);accounts,strategies=metadata(s,user.id)
    ids={x.instrument_id for x in orders}
    instruments={x.id:x for x in s.scalars(select(MarketInstrument).where(MarketInstrument.id.in_(ids)))} if ids else {}
    prices=cached_prices(s,user.id,orders,instruments);states=accounting(orders)
    order_rows=[];history=[];running=Decimal(0);open_count=0;priced_count=0
    for o in orders:
        account=accounts.get(o.account_id);strategy=strategies.get(o.strategy_id);instrument=instruments.get(o.instrument_id)
        state=states[o.id];tick=prices.get(o.instrument_key,{})
        price=Decimal(str(tick['ltp'])) if tick.get('ltp') is not None else None
        fresh=tick.get('data_status')=='LIVE' and price is not None
        mark=None
        if o.side=='BUY' and state['remaining']:
            open_count+=1
            if state['basis_known'] and fresh and state['entry_qty']:
                # Sum remaining FIFO lots below; entry average is not the cost
                # basis of the remaining position after partial exits.
                mark=price*state['remaining']-state['remaining_value'];running+=mark;priced_count+=1
        base={'id':o.id,'entry_time':utc(o.created_at),'trading_symbol':o.symbol,'instrument_key':o.instrument_key,'script':instrument.underlying or o.symbol if instrument else o.symbol,'group_service':strategy.name if strategy else 'Unavailable strategy','strategy_id':o.strategy_id,'client':user.name,'account_id':o.account_id,'quantity':o.quantity,'open_qty':state['remaining'] if o.side=='BUY' else 0,'filled_quantity':o.filled_quantity,'buy_price':o.average_price if o.side=='BUY' else None,'sl':None,'price':price,'price_status':tick.get('data_status','UNAVAILABLE'),'tp':None,'pnl':mark if o.side=='BUY' else state['sell_realized'] if state['basis_known'] and o.filled_quantity else None,'broker':account.broker if account else 'Unavailable broker','order_status':o.status,'bucket':GROUPS.get(o.status,'PENDING'),'reason':o.error_code,'side':o.side,'limit_price':o.price,'mode':'LIVE','basis_known':state['basis_known']}
        order_rows.append(base)
        if o.side=='BUY' and state['entry_qty']:
            exit_ids=sorted(state['exit_order_ids']);last_signal=max((utc(states[x]['order'].created_at) for x in exit_ids),default=None)
            history.append({**base,'signal_entry_time':utc(o.created_at),'signal_exit_time':last_signal,'first_fill_time':state['first_fill'],'last_exit_fill_time':state['last_exit'],'entry_qty':state['entry_qty'],'exit_qty':state['exit_qty'],'open_qty':state['remaining'],'entry_price':state['entry_value']/state['entry_qty'] if state['entry_value'] else o.average_price,'exit_price':state['exit_value']/state['exit_qty'] if state['exit_qty'] else None,'pnl':state['realized'] if state['basis_known'] else None,'unrealized_pnl':mark,'trade_status':('UNKNOWN' if not state['basis_known'] else 'CLOSED' if state['remaining']==0 else 'PARTIALLY_CLOSED' if state['exit_qty'] else 'OPEN'),'response':o.error_code or ('Broker fills reconciled' if o.reconciled_at else 'Reconciliation pending'),'exit_order_ids':exit_ids})
        elif o.side=='SELL' and state['unmatched_qty']:
            history.append({**base,'signal_entry_time':None,'signal_exit_time':utc(o.created_at),'entry_qty':None,'exit_qty':state['unmatched_qty'],'open_qty':None,'entry_price':None,'exit_price':state['unmatched_value']/state['unmatched_qty'] if state['unmatched_value'] else o.average_price,'pnl':None,'unrealized_pnl':None,'trade_status':'UNKNOWN','response':'Entry basis is not present in the tracked GNK fills.','exit_order_ids':[o.id]})
        elif not o.filled_quantity:
            history.append({**base,'signal_entry_time':utc(o.created_at),'signal_exit_time':None,'entry_qty':0,'exit_qty':0,'open_qty':0,'entry_price':None,'exit_price':None,'pnl':None,'unrealized_pnl':None,'trade_status':'NO_FILL','response':o.error_code or 'No reconciled broker fills.','exit_order_ids':[]})
    return order_rows,history,{'running_pnl':running if open_count==priced_count else None,'priced_open_entries':priced_count,'open_entries':open_count,'pnl_basis':'GROSS_FIFO_TRACKED_GNK_FILLS_EXCLUDES_CHARGES'}

def status_matches(row,status):
    value=(status or '').lower()
    if value in ('','all'):return True
    if value=='failed':return row['bucket']=='FAILED'
    if value=='errors':return bool(row.get('reason'))
    if value=='unauthorized':return any(x in (row.get('reason') or '') for x in ('AUTH','TOKEN_REJECTED','CREDENTIAL'))
    if value=='transit':return row['bucket']=='PENDING'
    aliases={'complete':'FILLED','completed':'FILLED','open':'OPEN','rejected':'REJECTED'}
    return row['order_status']==aliases.get(value,value.upper())

def filter_rows(rows,*,broker='',script='',strategy_id='',q='',status='',bucket='ALL',from_date=None,to_date=None):
    if from_date and to_date and from_date>to_date:raise HTTPException(422,'From date must not be after To date')
    from .accounting import IST
    result=[]
    for row in rows:
        stamp=row.get('signal_entry_time') or row.get('signal_exit_time') or row['entry_time']
        local=stamp.astimezone(IST).date()
        if from_date and local<from_date or to_date and local>to_date:continue
        if broker and row['broker']!=broker:continue
        if script and row['script'].casefold()!=script.casefold():continue
        if strategy_id and row['strategy_id']!=strategy_id:continue
        if bucket!='ALL' and row['bucket']!=bucket:continue
        if not status_matches(row,status):continue
        if q and q.casefold() not in ' '.join(str(row.get(k) or '') for k in ('trading_symbol','instrument_key','client','broker','group_service','order_status','reason')).casefold():continue
        result.append(row)
    return result

def paginate(rows,page,size,sort,direction):
    allowed={'entry_time','signal_entry_time','signal_exit_time','trading_symbol','group_service','client','quantity','entry_qty','exit_qty','buy_price','entry_price','exit_price','price','pnl','broker','order_status'}
    if sort not in allowed:raise HTTPException(422,'Unsupported sort column')
    present=[x for x in rows if x.get(sort) is not None];missing=[x for x in rows if x.get(sort) is None]
    present.sort(key=lambda x:(x[sort],x['id']),reverse=direction=='desc')
    rows=present+missing;offset=(page-1)*size
    return {'items':rows[offset:offset+size],'total':len(rows),'page':page,'page_size':size,'pages':max(1,(len(rows)+size-1)//size)}


def running_summary(rows,history=False):
    opened=[r for r in rows if r.get('open_qty') and r.get('side')=='BUY']
    field='unrealized_pnl' if history else 'pnl'
    priced=[r for r in opened if r.get(field) is not None]
    return {'running_pnl':sum((r[field] for r in priced),Decimal(0)) if len(opened)==len(priced) else None,'priced_open_entries':len(priced),'open_entries':len(opened),'pnl_basis':'GROSS_FIFO_TRACKED_GNK_FILLS_EXCLUDES_CHARGES'}
