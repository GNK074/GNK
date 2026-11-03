"""Gross FIFO accounting from reconciled GNK fills; never invent missing basis."""
from collections import defaultdict,deque
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
from app.execution.upstox import decimal,integer,ExecutionError
from app.core.config import now
IST=ZoneInfo('Asia/Kolkata')

def utc(value):return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)

def fill_time(value):
    if not isinstance(value,str) or not value.strip():return None
    try:
        try:result=datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:result=datetime.strptime(value,'%d-%b-%Y %H:%M:%S')
        result=result.replace(tzinfo=IST) if result.tzinfo is None else result
        result=result.astimezone(timezone.utc)
        return result if result<=now() else None
    except (ValueError,TypeError):return None

def accounting(orders):
    states={o.id:{'order':o,'entry_qty':0,'exit_qty':0,'entry_value':Decimal(0),'exit_value':Decimal(0),'remaining':0,'realized':Decimal(0),'sell_realized':Decimal(0),'basis_known':True,'first_fill':None,'last_exit':None,'exit_order_ids':set(),'remaining_value':Decimal(0),'unmatched_qty':0,'unmatched_value':Decimal(0)} for o in orders}
    events=[]
    for order in orders:
        state=states[order.id]
        if not order.filled_quantity:continue
        try:
            seen=set();parsed=[]
            for item in order.fills:
                tid=item.get('trade_id');qty=integer(item.get('quantity'));price=decimal(item.get('price'));stamp=fill_time(item.get('exchange_timestamp'))
                if not isinstance(tid,str) or tid in seen or qty<=0 or price<=0 or stamp is None:raise ValueError()
                seen.add(tid);parsed.append((stamp,utc(order.created_at),order.id,tid,qty,price))
            if sum(x[4] for x in parsed)!=order.filled_quantity:raise ValueError()
            events.extend(parsed)
        except (ExecutionError,ValueError,TypeError,AttributeError):
            state['basis_known']=False
            if order.side=='BUY':state['entry_qty']=order.filled_quantity;state['remaining']=order.filled_quantity
            else:state['unmatched_qty']=order.filled_quantity
    lots=defaultdict(deque)
    # If an earlier recorded fill has no chronology, attribution for its account
    # and instrument is uncertain. Do not assign a later sell an invented basis.
    uncertain={(x['order'].account_id,x['order'].instrument_key,x['order'].product) for x in states.values() if not x['basis_known']}
    for stamp,_,oid,tid,qty,price in sorted(events):
        state=states[oid];order=state['order'];key=(order.account_id,order.instrument_key,order.product)
        state['first_fill']=min(state['first_fill'] or stamp,stamp)
        if key in uncertain:state['basis_known']=False
        if order.side=='BUY':
            state['entry_qty']+=qty;state['remaining']+=qty;state['entry_value']+=qty*price;state['remaining_value']+=qty*price
            lots[key].append({'state':state,'remaining':qty,'price':price})
        else:
            left=qty
            while left and lots[key]:
                lot=lots[key][0];take=min(left,lot['remaining']);entry=lot['state']
                entry['remaining_value']-=take*lot['price'];entry['exit_qty']+=take;entry['exit_value']+=take*price;entry['remaining']-=take;entry['realized']+=take*(price-lot['price']);entry['last_exit']=stamp;entry['exit_order_ids'].add(oid)
                state['sell_realized']+=take*(price-lot['price'])
                lot['remaining']-=take;left-=take
                if not lot['remaining']:lots[key].popleft()
            if left:
                state['basis_known']=False;state['unmatched_qty']+=left;state['unmatched_value']+=left*price
    return states
