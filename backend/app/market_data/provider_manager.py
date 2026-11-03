"""Cross-process singleton feed manager. Reconnect restores the database-derived set."""
import asyncio,random,time
from collections import defaultdict
from app.core.config import now
from app.market_data.normalizer import normalize_tick,InvalidMarketData
from app.market_data.providers.upstox.protobuf_decoder import decode
from app.market_data.providers.base import ProviderError
from app.market_data.config import market_settings as cfg

class FeedManager:
    def __init__(self,provider,store,owner,desired,enabled,consume=None,persist_status=None):
        self.provider=provider;self.store=store;self.owner=owner;self.desired=desired;self.enabled=enabled
        self.queue=asyncio.Queue(maxsize=cfg.marketdata_queue_size);self.consume=consume or self.default_consume
        self.persist_status=persist_status
        self.active={};self.segments={};self.last_message=None;self.dropped=0;self.invalid=0;self.attempt=0
    async def default_consume(self,tick):return await asyncio.to_thread(self.store.put_tick,tick,self.owner)
    async def state(self,status,error=None):
        await asyncio.to_thread(self.store.set_state,self.owner,{'state':status,'segments':self.segments,'last_message_at':self.last_message,'error_code':error,'dropped':self.dropped,'invalid_frames':self.invalid,'subscriptions':len(self.active),'reconnect_attempt':self.attempt})
        if self.persist_status:await asyncio.to_thread(self.persist_status,status,self.last_message,error)
    async def restore(self):
        desired=await asyncio.to_thread(self.desired)
        obsolete=[key for key in self.active if key not in desired]
        if obsolete:await self.provider.unsubscribe(obsolete)
        groups=defaultdict(list)
        for key,mode in desired.items():
            if self.active.get(key)!=mode:groups[mode].append(key)
        for mode,keys in groups.items():
            for offset in range(0,len(keys),100):await self.provider.subscribe(keys[offset:offset+100],mode)
        self.active=desired
    async def receive(self):
        while True:
            raw=await asyncio.wait_for(self.provider.socket.recv(),timeout=60)
            self.last_message=now().isoformat()
            try:
                message=await asyncio.to_thread(decode,raw)
                if message.get('marketInfo'):
                    self.segments=message['marketInfo'].get('segmentStatus',{})
                    continue
                for key,value in message.get('feeds',{}).items():
                    if key not in self.active:continue
                    try:
                        tick=normalize_tick(key,value,message.get('currentTs'))
                        if self.queue.full():self.queue.get_nowait();self.queue.task_done();self.dropped+=1
                        self.queue.put_nowait(tick)
                    except InvalidMarketData:self.invalid+=1
            except ProviderError:self.invalid+=1
    async def publish(self):
        while True:
            tick=await self.queue.get()
            try:
                if not await asyncio.to_thread(self.store.owns,self.owner):raise ProviderError('LEADERSHIP_LOST')
                await self.consume(tick)
            finally:self.queue.task_done()
    async def monitor(self):
        while True:
            if not await asyncio.to_thread(self.enabled) or not await asyncio.to_thread(self.store.owns,self.owner):raise ProviderError('PROVIDER_DISABLED_OR_LEASE_LOST')
            await self.restore();await self.state('CONNECTED');await asyncio.sleep(2)
    async def run(self):
        while await asyncio.to_thread(self.store.owns,self.owner):
            if not await asyncio.to_thread(self.enabled):
                await self.state('DISABLED');await asyncio.sleep(2);continue
            tasks=[];connected_at=None
            try:
                self.active={};self.segments={};await self.state('CONNECTING')
                await self.provider.connect();await self.restore();connected_at=time.monotonic()
                tasks=[asyncio.create_task(self.receive()),asyncio.create_task(self.publish()),asyncio.create_task(self.monitor())]
                done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_EXCEPTION)
                for task in done:task.result()
            except asyncio.CancelledError:raise
            except Exception:
                if connected_at and time.monotonic()-connected_at>60:self.attempt=0
                self.attempt+=1
                await self.state('RECONNECTING','PROVIDER_STREAM_UNAVAILABLE')
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
                await self.provider.disconnect()
                while not self.queue.empty():self.queue.get_nowait();self.queue.task_done()
            await asyncio.sleep(min(60,2**min(self.attempt,5))+random.random())
