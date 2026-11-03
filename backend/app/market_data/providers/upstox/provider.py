import asyncio,json,logging
from websockets.asyncio.client import connect as ws_connect
from app.market_data.providers.base import MarketDataProvider,ProviderError
from .client import UpstoxClient
from .websocket import authorize
from .quotes import quotes
from .historical import historical,intraday
from .instrument_master import download
class UpstoxProvider(MarketDataProvider):
    def __init__(self,token,store,transport=None,connector=ws_connect):
        self.client=UpstoxClient(token,store,transport);self.socket=None;self.connector=connector
        self.logger=logging.getLogger('gnk.marketdata.provider_socket');self.logger.addHandler(logging.NullHandler());self.logger.propagate=False
    async def connect(self):
        url=await authorize(self.client)
        try:self.socket=await self.connector(url,max_size=4*1024*1024,max_queue=16,ping_interval=20,ping_timeout=20,close_timeout=5,proxy=None,logger=self.logger)
        except Exception:raise ProviderError('PROVIDER_WEBSOCKET_CONNECT_FAILED') from None
    async def disconnect(self):
        if self.socket:
            try:await self.socket.close()
            except Exception:pass
            self.socket=None
    async def command(self,method,keys,mode='ltpc'):
        if not self.socket:raise ProviderError('PROVIDER_DISCONNECTED')
        await self.socket.send(json.dumps({'guid':__import__('uuid').uuid4().hex,'method':method,'data':{'mode':mode,'instrumentKeys':keys}}).encode())
    async def subscribe(self,keys,mode):await self.command('sub',keys,mode)
    async def unsubscribe(self,keys):await self.command('unsub',keys)
    async def get_quotes(self,keys):return await quotes(self.client,keys)
    async def get_historical_candles(self,key,interval,start,end):return await historical(self.client,key,interval,start,end)
    async def get_intraday_candles(self,key,interval):return await intraday(self.client,key,interval)
    async def get_instruments(self):
        records,version=await download('complete.json.gz',self.client.transport)
        suspended,_=await download('suspended-instrument.json.gz',self.client.transport)
        return records,suspended,version
    async def health_check(self):
        await authorize(self.client)
        return {'authorized':True,'provider':'upstox'}
