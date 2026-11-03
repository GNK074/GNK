"""Provider-independent normalization. Missing provider fields stay null."""
import math
from datetime import datetime,timezone
from app.core.config import now

class InvalidMarketData(ValueError): pass

def number(value,negative=False):
    if value is None or isinstance(value,bool):return None
    try:
        value=float(value)
        if not math.isfinite(value) or (value<0 and not negative):raise ValueError()
        return value
    except (TypeError,ValueError,OverflowError):raise InvalidMarketData('INVALID_NUMBER') from None

def timestamp(value):
    if value in (None,'',0,'0'):return None
    try:
        if isinstance(value,(int,float)) or str(value).isdigit():
            dt=datetime.fromtimestamp(float(value)/1000,timezone.utc)
        else:dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo is None:raise ValueError()
        dt=dt.astimezone(timezone.utc)
        if dt.timestamp()>now().timestamp()+5:raise ValueError()
        return dt.isoformat()
    except (ValueError,TypeError,OverflowError,OSError):raise InvalidMarketData('INVALID_TIMESTAMP') from None

def normalize_tick(key,feed,envelope_ts=None,symbol=None):
    full=feed.get('fullFeed',{})
    body=full.get('marketFF') or full.get('indexFF') or feed.get('firstLevelWithGreeks') or {}
    ltpc=feed.get('ltpc') or body.get('ltpc') or {}
    depth=body.get('marketLevel',{}).get('bidAskQuote',[])
    if body.get('firstDepth'):depth=[body['firstDepth']]
    day=next((x for x in body.get('marketOHLC',{}).get('ohlc',[]) if x.get('interval')=='1d'),{})
    tick={'provider':'upstox','exchange':key.split('_')[0],'instrument_key':key,'symbol':symbol,
        'ltp':number(ltpc.get('ltp')),'ltq':number(ltpc.get('ltq')),'ltt':timestamp(ltpc.get('ltt')),
        'close':number(ltpc.get('cp')),'volume':number(body.get('vtt')),'average_price':number(body.get('atp')),
        'open':number(day.get('open')),'high':number(day.get('high')),'low':number(day.get('low')),
        'oi':number(body.get('oi')),'bid':[],'ask':[],
        'greeks':{k:number(v,True) for k,v in body.get('optionGreeks',{}).items()},
        'provider_timestamp':timestamp(envelope_ts),'received_at':now().isoformat(),'data_status':'UNVERIFIED','source':'UPSTOX_V3'}
    if body.get('iv') is not None:tick['greeks']['iv']=number(body['iv'])
    for quote in depth[:5]:
        if quote.get('bidP') is not None:tick['bid'].append({'price':number(quote['bidP']),'quantity':number(quote.get('bidQ'))})
        if quote.get('askP') is not None:tick['ask'].append({'price':number(quote['askP']),'quantity':number(quote.get('askQ'))})
    return tick

def normalize_quote(key,quote,symbol=None):
    ohlc=quote.get('ohlc') or {}
    tick=normalize_tick(key,{'ltpc':{'ltp':quote.get('last_price'),'ltt':quote.get('last_trade_time'),'ltq':quote.get('last_quantity'),'cp':ohlc.get('close')}},quote.get('timestamp'),symbol)
    tick.update(volume=number(quote.get('volume')),average_price=number(quote.get('average_price')),oi=number(quote.get('oi')),open=number(ohlc.get('open')),high=number(ohlc.get('high')),low=number(ohlc.get('low')),data_status='SNAPSHOT',source='UPSTOX_REST')
    for side in ('buy','sell'):
        tick['bid' if side=='buy' else 'ask']=[{'price':number(x.get('price')),'quantity':number(x.get('quantity'))} for x in quote.get('depth',{}).get(side,[])[:5]]
    return tick
