from urllib.parse import urlsplit
from app.market_data.providers.base import ProviderError
async def authorize(client):
    data=await client.get('/v3/feed/market-data-feed/authorize')
    url=data.get('authorized_redirect_uri','')
    try:
        parsed=urlsplit(url)
        port=parsed.port
    except (ValueError,TypeError):raise ProviderError('INVALID_AUTHORIZED_WEBSOCKET_HOST') from None
    if parsed.scheme!='wss' or not parsed.hostname or not parsed.hostname.endswith('.upstox.com') or parsed.username or port not in (None,443):
        raise ProviderError('INVALID_AUTHORIZED_WEBSOCKET_HOST')
    return url
