import gzip,hashlib,io,json
from datetime import datetime
from zoneinfo import ZoneInfo
import httpx
from app.core.config import now,ident
from app.market_data.models import MarketInstrument
from app.market_data.normalizer import number,InvalidMarketData
from app.market_data.providers.base import ProviderError
from app.market_data.persistence import upsert
URL='https://assets.upstox.com/market-quote/instruments/exchange/'
SUPPORTED={'NSE_EQ','BSE_EQ','NSE_FO','BSE_FO','NSE_INDEX','BSE_INDEX'}
async def download(name,transport=None):
    if name not in ('complete.json.gz','suspended-instrument.json.gz'):raise ProviderError('INVALID_MASTER_FILE')
    async with httpx.AsyncClient(timeout=60,transport=transport,follow_redirects=False,trust_env=False) as client:
        async with client.stream('GET',URL+name) as response:
            if response.status_code!=200:raise ProviderError('INSTRUMENT_DOWNLOAD_FAILED')
            buf=bytearray()
            async for part in response.aiter_bytes():
                buf.extend(part)
                if len(buf)>32*1024*1024:raise ProviderError('INSTRUMENT_FILE_TOO_LARGE')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(buf)) as source:
            raw=source.read(256*1024*1024+1)
        if len(raw)>256*1024*1024:raise ValueError()
        rows=json.loads(raw)
        if not isinstance(rows,list) or (not rows and name=='complete.json.gz') or len(rows)>500000:raise ValueError()
        return rows,hashlib.sha256(raw).hexdigest()
    except (ValueError,OSError,EOFError):raise ProviderError('INVALID_INSTRUMENT_FILE') from None

def parse_instrument(row,version,suspended=False):
    segment=row.get('segment')
    if segment not in SUPPORTED:return None
    key=row.get('instrument_key');symbol=row.get('trading_symbol')
    if not isinstance(key,str) or not key.startswith(segment+'|') or len(key)>200 or not symbol or len(symbol)>100:raise InvalidMarketData('INVALID_INSTRUMENT')
    expiry=None
    if row.get('expiry'):
        expiry=datetime.fromtimestamp(float(row['expiry'])/1000,ZoneInfo('Asia/Kolkata')).date()
    status='SUSPENDED' if suspended else 'EXPIRED' if expiry and expiry<now().astimezone(ZoneInfo('Asia/Kolkata')).date() else 'ACTIVE'
    lot=number(row.get('lot_size'))
    if lot is not None and (lot!=int(lot) or lot<1):raise InvalidMarketData('INVALID_LOT_SIZE')
    for field,maximum in (('name',250),('instrument_type',30),('underlying_symbol',150),('underlying_key',150),('asset_symbol',150)):
        if row.get(field) is not None and (not isinstance(row[field],str) or len(row[field])>maximum):raise InvalidMarketData('INVALID_INSTRUMENT')
    return dict(id=ident(),provider='upstox',instrument_key=key,exchange=segment[:3],segment=segment,symbol=symbol,name=row.get('name') or symbol,instrument_type=row.get('instrument_type') or ('INDEX' if segment.endswith('INDEX') else 'UNKNOWN'),expiry=expiry,strike=number(row.get('strike_price')),lot_size=int(lot) if lot is not None else None,tick_size=number(row.get('tick_size')),underlying=row.get('underlying_symbol') or row.get('underlying_key') or row.get('asset_symbol'),status=status,version=version,synced_at=now())

def store_master(s,records,suspended,version):
    from sqlalchemy import update
    suspended_keys={r.get('instrument_key') for r in suspended}
    normalized=[]
    complete_keys={r.get('instrument_key') for r in records}
    for row in records+[r for r in suspended if r.get('instrument_key') not in complete_keys]:
        item=parse_instrument(row,version,row.get('instrument_key') in suspended_keys)
        if item:normalized.append(item)
    if not normalized:raise ProviderError('EMPTY_SUPPORTED_MASTER')
    upsert(s,MarketInstrument,normalized,['instrument_key'])
    s.execute(update(MarketInstrument).where(MarketInstrument.provider=='upstox',MarketInstrument.version!=version,MarketInstrument.status=='ACTIVE').values(status='UNLISTED'))
    s.execute(update(MarketInstrument).where(MarketInstrument.expiry<now().astimezone(ZoneInfo('Asia/Kolkata')).date(),MarketInstrument.status.in_(['ACTIVE','UNLISTED'])).values(status='EXPIRED'))
    return len(normalized)
