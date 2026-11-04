"""Bounded import of official Dhan Indian equity metadata into provider namespace."""
import csv,hashlib,io
from datetime import timedelta
from decimal import Decimal
import httpx
from sqlalchemy import select,update
from app.core.config import ident,now
from app.market_data.models import MarketInstrument
from app.market_data.persistence import upsert
from .client import DhanError
MASTER_URL='https://images.dhan.co/api-data/api-scrip-master.csv'

def key(segment,security_id):return f'DHAN|{segment}|{security_id}'
def parse(lines):
    reader=csv.DictReader(lines);result=[];seen=set()
    required={'SEM_EXM_EXCH_ID','SEM_SEGMENT','SEM_SMST_SECURITY_ID','SEM_INSTRUMENT_NAME','SEM_TRADING_SYMBOL','SEM_LOT_UNITS','SEM_TICK_SIZE'}
    if not required<=set(reader.fieldnames or []):raise DhanError('INVALID_DHAN_MASTER_SCHEMA')
    for row in reader:
        exchange=row['SEM_EXM_EXCH_ID'].strip();segment=row['SEM_SEGMENT'].strip();kind=row['SEM_INSTRUMENT_NAME'].strip()
        if exchange not in ('NSE','BSE') or segment!='E' or kind not in ('EQUITY','EQ'):continue
        sid=row['SEM_SMST_SECURITY_ID'].strip();symbol=row['SEM_TRADING_SYMBOL'].strip()
        try:tick=Decimal(row['SEM_TICK_SIZE']);lot=Decimal(row['SEM_LOT_UNITS'])
        except Exception:raise DhanError('INVALID_DHAN_MASTER_NUMBER') from None
        if not sid.isdigit() or len(sid)>12 or not symbol or len(symbol)>100 or not tick.is_finite() or tick<=0 or lot!=1:continue
        k=key(exchange+'_EQ',sid)
        if k in seen:raise DhanError('DUPLICATE_DHAN_INSTRUMENT')
        seen.add(k);result.append(dict(id=ident(),provider='dhan',instrument_key=k,exchange=exchange,segment=exchange+'_EQ',symbol=symbol,name=(row.get('SEM_CUSTOM_SYMBOL') or symbol)[:250],instrument_type='EQ',expiry=None,strike=None,lot_size=1,tick_size=tick,underlying=None,status='ACTIVE',version='pending',synced_at=now()))
        if len(result)>50000:raise DhanError('DHAN_MASTER_TOO_LARGE')
    if not result:raise DhanError('EMPTY_DHAN_EQUITY_MASTER')
    return result

def download(transport=None):
    size=0
    def lines(response):
        nonlocal size
        for line in response.iter_lines():
            size+=len(line.encode('utf-8'))
            if size>100_000_000 or len(line)>10000:raise DhanError('DHAN_MASTER_TOO_LARGE')
            yield line
    try:
        with httpx.Client(timeout=30,transport=transport,follow_redirects=False,trust_env=False) as client:
            with client.stream('GET',MASTER_URL) as response:
                if response.status_code!=200:raise DhanError('DHAN_MASTER_UNAVAILABLE')
                data=parse(lines(response))
    except DhanError:raise
    except Exception:raise DhanError('DHAN_MASTER_UNAVAILABLE') from None
    version=hashlib.sha256(('\n'.join(sorted(r['instrument_key']+':'+str(r['tick_size']) for r in data))).encode()).hexdigest()
    for r in data:r['version']=version
    return data

def store(s,rows):
    # Update in the caller's transaction. A failed import leaves the old master.
    s.execute(update(MarketInstrument).where(MarketInstrument.provider=='dhan').values(status='INACTIVE'))
    upsert(s,MarketInstrument,rows,['instrument_key']);s.flush()
    return len(rows)
