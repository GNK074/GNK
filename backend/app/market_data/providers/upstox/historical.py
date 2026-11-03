from datetime import datetime,timedelta,timezone
from urllib.parse import quote
from app.market_data.schemas import INTERVALS
from app.market_data.normalizer import number,InvalidMarketData
from app.market_data.providers.base import ProviderError
from app.core.config import ident,now
from app.market_data.models import MarketCandle
from app.market_data.persistence import upsert

def windows(start,end,interval):
    unit,count=INTERVALS[interval]
    days=28 if unit=='minutes' and count<=15 else 84 if unit in ('minutes','hours') else 3650
    while start<=end:
        stop=min(end,start+timedelta(days=days-1));yield start,stop;start=stop+timedelta(days=1)

def parse_candle(raw,instrument,interval):
    if not isinstance(raw,list) or len(raw)<6:raise InvalidMarketData('INVALID_CANDLE')
    try:
        timestamp=datetime.fromisoformat(raw[0])
        if timestamp.tzinfo is None or timestamp>now()+timedelta(seconds=5):raise ValueError()
        o,h,l,c=[number(x) for x in raw[1:5]]
        if any(x is None for x in (o,h,l,c)) or h<max(o,c,l) or l>min(o,c,h):raise ValueError()
        return dict(id=ident(),instrument_id=instrument.id,exchange=instrument.exchange,timestamp=timestamp.astimezone(timezone.utc),exchange_timestamp=raw[0],open=o,high=h,low=l,close=c,volume=number(raw[5]),oi=number(raw[6]) if len(raw)>6 else None,interval=interval,provider='upstox',source='UPSTOX_V3',quality='VALIDATED')
    except (ValueError,TypeError):raise InvalidMarketData('INVALID_CANDLE') from None

async def historical(client,key,interval,start,end):
    unit,count=INTERVALS[interval]
    data=await client.get(f'/v3/historical-candle/{quote(key,safe="")}/{unit}/{count}/{end.isoformat()}/{start.isoformat()}')
    candles=data.get('candles')
    if not isinstance(candles,list) or len(candles)>50000:raise ProviderError('INVALID_CANDLE_RESPONSE')
    return candles
async def intraday(client,key,interval):
    unit,count=INTERVALS[interval]
    if unit not in ('minutes','hours','days'):raise ProviderError('INVALID_INTRADAY_INTERVAL')
    data=await client.get(f'/v3/historical-candle/intraday/{quote(key,safe="")}/{unit}/{count}')
    candles=data.get('candles')
    if not isinstance(candles,list) or len(candles)>50000:raise ProviderError('INVALID_CANDLE_RESPONSE')
    return candles

def store_candles(s,raw,instrument,interval):
    rows=[parse_candle(row,instrument,interval) for row in raw]
    unique={row['timestamp']:row for row in rows}
    upsert(s,MarketCandle,list(unique.values()),['instrument_id','provider','interval','timestamp'])
    return len(unique)
