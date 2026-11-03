import asyncio,random
from urllib.parse import quote
import httpx
from app.market_data.config import market_settings as cfg
from app.market_data.providers.base import ProviderError
class UpstoxClient:
    def __init__(self,token,store,transport=None):self._token=token;self.store=store;self.transport=transport
    async def get(self,path,params=None):
        if not path.startswith(('/v3/historical-candle/','/v3/feed/market-data-feed/authorize','/v2/market-quote/quotes','/v2/market/')):
            raise ProviderError('READ_ONLY_ENDPOINT_REQUIRED')
        for attempt in range(3):
            if not await asyncio.to_thread(self.store.provider_request_allowed):raise ProviderError('PROVIDER_RATE_LIMIT')
            try:
                async with httpx.AsyncClient(base_url=cfg.upstox_api_base_url,timeout=20,transport=self.transport,follow_redirects=False,trust_env=False) as client:
                    r=await client.get(path,params=params,headers={'Authorization':'Bearer '+self._token,'Accept':'application/json'})
                if r.status_code in (401,403):raise ProviderError('PROVIDER_AUTHORIZATION_FAILED')
                if r.status_code==429 or r.status_code>=500:
                    if attempt<2:
                        await asyncio.sleep(min(10,2**attempt+random.random()));continue
                    raise ProviderError('PROVIDER_RATE_LIMIT' if r.status_code==429 else 'PROVIDER_UNAVAILABLE')
                if r.status_code!=200:raise ProviderError('PROVIDER_REQUEST_REJECTED')
                data=r.json()
                if data.get('status')!='success' or not isinstance(data.get('data'),dict):raise ProviderError('INVALID_PROVIDER_RESPONSE')
                return data['data']
            except ProviderError:raise
            except (httpx.HTTPError,ValueError,TypeError):
                if attempt==2:raise ProviderError() from None
                await asyncio.sleep(2**attempt)
        raise ProviderError()
