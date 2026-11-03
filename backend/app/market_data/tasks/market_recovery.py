"""Recover snapshots without labeling them as a live stream."""
from app.market_data.normalizer import normalize_quote
async def recover(provider,keys,store,owner):
    for offset in range(0,len(keys),100):
        batch=keys[offset:offset+100]
        raw=await provider.get_quotes(batch)
        for item in raw.values():
            key=item.get('instrument_token')
            if key in batch:
                await __import__('asyncio').to_thread(store.put_tick,normalize_quote(key,item),owner)
