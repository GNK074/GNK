from app.market_data.providers.base import ProviderError
async def quotes(client,keys):
    if not keys or len(keys)>100:raise ProviderError('INVALID_QUOTE_BATCH')
    return await client.get('/v2/market-quote/quotes',{'instrument_key':','.join(keys)})
