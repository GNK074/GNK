"""Deterministic research indicators, never a trained ML prediction or order."""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
from .client import DhanError

def dec(v):
    if v is None or isinstance(v,bool):return None
    try:
        d=Decimal(str(v))
        return d if d.is_finite() else None
    except Exception:return None

def candles(data):
    if not isinstance(data,dict):raise DhanError('INVALID_DHAN_CANDLES')
    keys=('timestamp','open','high','low','close');length=len(data.get('timestamp',[]))
    if length>10000 or any(not isinstance(data.get(k),list) or len(data[k])!=length for k in keys):raise DhanError('INVALID_DHAN_CANDLES')
    result=[];seen=set()
    for i in range(length):
        stamp=dec(data['timestamp'][i]);values={k:dec(data[k][i]) for k in keys[1:]}
        if stamp is None or stamp!=int(stamp) or int(stamp) in seen or any(v is None or v<0 for v in values.values()):raise DhanError('INVALID_DHAN_CANDLES')
        if values['high']<max(values['open'],values['close'],values['low']) or values['low']>min(values['open'],values['close']):raise DhanError('INVALID_DHAN_CANDLES')
        seen.add(int(stamp));volume=dec(data['volume'][i]) if isinstance(data.get('volume'),list) and len(data['volume'])==length else None
        result.append(dict(timestamp=int(stamp),**values,volume=volume,oi=dec(data['open_interest'][i]) if isinstance(data.get('open_interest'),list) and len(data['open_interest'])==length else None,complete=True))
    return sorted(result,key=lambda r:r['timestamp'])

def aggregate(rows,minutes,base=1):
    groups={};ist=ZoneInfo('Asia/Kolkata')
    for r in rows:
        local=datetime.fromtimestamp(r['timestamp'],timezone.utc).astimezone(ist)
        anchor=local.replace(hour=9,minute=15,second=0,microsecond=0)
        bucket=int(anchor.timestamp())+((r['timestamp']-int(anchor.timestamp()))//(minutes*60))*(minutes*60)
        groups.setdefault(bucket,[]).append(r)
    out=[]
    for stamp,group in sorted(groups.items()):
        consecutive=len(group)==minutes//base and all(r['timestamp']==stamp+i*base*60 for i,r in enumerate(group))
        out.append(dict(timestamp=stamp,open=group[0]['open'],high=max(r['high'] for r in group),low=min(r['low'] for r in group),close=group[-1]['close'],volume=sum((r['volume'] for r in group),Decimal(0)) if all(r['volume'] is not None for r in group) else None,oi=group[-1]['oi'],complete=consecutive))
    return out

def ema(values,period):
    result=[];current=None;alpha=Decimal(2)/(period+1)
    for i,v in enumerate(values):
        current=v if current is None else alpha*v+(1-alpha)*current
        result.append(current if i>=period-1 else None)
    return result

def indicators(rows):
    rows=[r for r in rows if r['complete']];closes=[r['close'] for r in rows]
    if not rows:return {'status':'INSUFFICIENT_DATA','ml_model_status':'NOT_CONFIGURED','order_submitted':False}
    result={f'ema_{n}':ema(closes,n)[-1] for n in (9,20,60)}
    gains=[max(closes[i]-closes[i-1],Decimal(0)) for i in range(1,len(closes))];losses=[max(closes[i-1]-closes[i],Decimal(0)) for i in range(1,len(closes))]
    def wilder(values,n):
        if len(values)<n:return None
        avg=sum(values[:n],Decimal(0))/n
        for v in values[n:]:avg=(avg*(n-1)+v)/n
        return avg
    gain=wilder(gains,14);loss=wilder(losses,14)
    result['rsi_14']=None if gain is None else Decimal(50) if gain==loss==0 else Decimal(100) if loss==0 else Decimal(100)-Decimal(100)/(1+gain/loss)
    tr=[max(r['high']-r['low'],abs(r['high']-rows[i-1]['close']),abs(r['low']-rows[i-1]['close'])) for i,r in enumerate(rows) if i]
    result['atr_14']=wilder(tr,14)
    e12=ema(closes,12);e26=ema(closes,26);macd=[a-b for a,b in zip(e12,e26) if a is not None and b is not None]
    result['macd']=macd[-1] if macd else None;signal=ema(macd,9);result['macd_signal']=signal[-1] if signal else None
    day=datetime.fromtimestamp(rows[-1]['timestamp'],ZoneInfo('Asia/Kolkata')).date()
    same=[r for r in rows if datetime.fromtimestamp(r['timestamp'],ZoneInfo('Asia/Kolkata')).date()==day]
    total=sum((r['volume'] for r in same),Decimal(0)) if all(r['volume'] is not None for r in same) else None
    result['vwap']=sum(((r['high']+r['low']+r['close'])/3*r['volume'] for r in same),Decimal(0))/total if total else None
    result['support']=min(r['low'] for r in rows[-20:]);result['resistance']=max(r['high'] for r in rows[-20:])
    recent=rows[-21:-1]
    result['volume_breakout']=None if len(recent)<20 or rows[-1]['volume'] is None or any(r['volume'] is None for r in recent) else rows[-1]['volume']>sum((r['volume'] for r in recent),Decimal(0))/20*Decimal('1.5')
    result['trend']=None if result['ema_20'] is None else 'UP' if result['ema_9']>result['ema_20'] else 'DOWN' if result['ema_9']<result['ema_20'] else 'FLAT'
    result.update(status='READY' if len(rows)>=60 else 'PARTIAL_WARMUP',basis='DETERMINISTIC_TECHNICAL_RESEARCH',ml_model_status='NOT_CONFIGURED',confidence=None,order_submitted=False)
    return result
