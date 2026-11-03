"""Single leased worker for stream, synchronization and snapshot recovery."""
import asyncio,json,time,uuid
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select,update,delete
from app.core.config import now
from app.database.session import DB,engine
from app.database.readiness import check_schema
from app.database.tenancy import set_market_worker
from app.market_data.config import market_settings as cfg
from app.market_data.models import MarketProviderStatus,MarketSyncJob,MarketInstrument,MarketTickLatest
from app.market_data.service import get_store,provider
from app.market_data.subscription_manager import provider_status,active_provider_subscriptions
from app.market_data.providers.upstox.auth import synchronize_secret
from app.market_data.providers.upstox.instrument_master import store_master
from app.market_data.providers.upstox.historical import windows,store_candles
from app.market_data.provider_manager import FeedManager
from app.market_data.tasks.market_recovery import recover
from app.market_data.tasks.instrument_sync import enqueue_instruments
from app.market_data.schemas import HistoryInput
from app.market_data.persistence import upsert

class MarketWorker:
    def __init__(self,store=None):self.store=store or get_store();self.owner=uuid.uuid4().hex;self.last_persist={}
    def enabled(self,websocket=False):
        with DB() as s:
            row=s.get(MarketProviderStatus,'upstox')
            return cfg.upstox_enabled and bool(row and row.enabled) and (not websocket or cfg.upstox_websocket_enabled)
    def desired(self):
        with DB() as s:return active_provider_subscriptions(s)
    def fenced_commit(self,s):
        if not self.store.owns(self.owner):raise RuntimeError('LEADERSHIP_LOST')
        s.commit()
    def initialize(self):
        with DB() as s:
            set_market_worker(s);provider_status(s);synchronize_secret(s)
            s.execute(update(MarketSyncJob).where(MarketSyncJob.state=='RUNNING').values(state='QUEUED',error_code='RECOVERED_AFTER_RESTART'))
            self.fenced_commit(s)
    def persist_status(self,state,last_message,error):
        with DB() as s:
            row=provider_status(s);row.state=state;row.last_message_at=datetime.fromisoformat(last_message) if last_message else None;row.error_code=error;row.updated=now();self.fenced_commit(s)
    async def renew(self):
        while True:
            await asyncio.sleep(cfg.marketdata_worker_lease_seconds/3)
            if not await asyncio.to_thread(self.store.renew,self.owner):raise RuntimeError('LEADERSHIP_LOST')
    def make_provider(self):
        with DB() as s:return provider(s,self.store)
    def claim(self):
        with DB() as s:
            set_market_worker(s)
            job=s.scalar(select(MarketSyncJob).where(MarketSyncJob.state=='QUEUED').order_by(MarketSyncJob.created).with_for_update(skip_locked=True).limit(1))
            if not job:return None
            job.state='RUNNING';job.started=now();job.error_code=None
            self.fenced_commit(s)
            return job.id,job.kind,job.parameters
    def finish(self,job_id,processed=0,error=None):
        with DB() as s:
            row=s.get(MarketSyncJob,job_id)
            row.state='FAILED' if error else 'COMPLETED';row.processed=processed;row.error_code=error;row.finished=now()
            self.fenced_commit(s)
    def write_master(self,data):
        with DB() as s:
            count=store_master(s,*data);self.fenced_commit(s);return count
    def candle_instrument(self,id):
        with DB() as s:
            row=s.get(MarketInstrument,id)
            if not row:raise ValueError('INSTRUMENT_MISSING')
            return row
    def write_candles(self,raw,instrument,interval):
        with DB() as s:
            count=store_candles(s,raw,instrument,interval);self.fenced_commit(s);return count
    async def jobs(self):
        last_schedule=None
        while True:
            if await asyncio.to_thread(self.enabled):
                local=now().astimezone(ZoneInfo('Asia/Kolkata'))
                if cfg.upstox_instrument_sync_enabled and local.hour>=6 and last_schedule!=local.date():
                    def schedule():
                        with DB() as s:
                            latest=s.scalar(select(MarketSyncJob).where(MarketSyncJob.kind=='INSTRUMENTS',MarketSyncJob.state=='COMPLETED').order_by(MarketSyncJob.finished.desc()).limit(1))
                            if not latest or latest.finished.date()!=now().date():enqueue_instruments(s)
                            self.fenced_commit(s)
                    await asyncio.to_thread(schedule);last_schedule=local.date()
                claim=await asyncio.to_thread(self.claim)
                if claim:
                    job_id,kind,params=claim
                    try:
                        p=await asyncio.to_thread(self.make_provider)
                        if kind=='INSTRUMENTS':
                            data=await p.get_instruments();count=await asyncio.to_thread(self.write_master,data)
                        else:
                            if not cfg.upstox_historical_sync_enabled:raise ValueError('HISTORY_DISABLED')
                            data=HistoryInput(**params);instrument=await asyncio.to_thread(self.candle_instrument,data.instrument_id);count=0
                            for start,end in windows(data.from_date,data.to_date,data.interval):
                                raw=await (p.get_intraday_candles(instrument.instrument_key,data.interval) if kind=='INTRADAY' else p.get_historical_candles(instrument.instrument_key,data.interval,start,end))
                                count+=await asyncio.to_thread(self.write_candles,raw,instrument,data.interval)
                                if kind=='INTRADAY':break
                        await asyncio.to_thread(self.finish,job_id,count)
                    except asyncio.CancelledError:raise
                    except Exception as error:
                        await asyncio.to_thread(self.finish,job_id,0,getattr(error,'code','SYNC_VALIDATION_FAILED'))
            await asyncio.sleep(2)
    async def consume(self,tick):
        result=await asyncio.to_thread(self.store.put_tick,tick,self.owner)
        if result==1 and cfg.marketdata_tick_persist_seconds:
            key=tick['instrument_key'];last=self.last_persist.get(key,0)
            if time.monotonic()-last>=cfg.marketdata_tick_persist_seconds:
                def persist():
                    with DB() as s:
                        if not s.scalar(select(MarketInstrument.id).where(MarketInstrument.instrument_key==key)):return
                        upsert(s,MarketTickLatest,[{'instrument_key':key,'payload':tick,'received_at':datetime.fromisoformat(tick['received_at']),'expires_at':now()+timedelta(hours=cfg.marketdata_tick_retention_hours)}],['instrument_key'])
                        s.execute(delete(MarketTickLatest).where(MarketTickLatest.expires_at<now()))
                        self.fenced_commit(s)
                await asyncio.to_thread(persist);self.last_persist[key]=time.monotonic()
    async def snapshots(self):
        while True:
            await asyncio.sleep(30)
            def prune():
                with DB() as s:
                    s.execute(delete(MarketTickLatest).where(MarketTickLatest.expires_at<now()));self.fenced_commit(s)
            await asyncio.to_thread(prune)
            if await asyncio.to_thread(self.enabled) and cfg.marketdata_distribution_approved:
                keys=await asyncio.to_thread(self.desired)
                missing=[]
                for key in keys:
                    tick=await asyncio.to_thread(self.store.latest,key)
                    if not tick or (now()-datetime.fromisoformat(tick['received_at'])).total_seconds()>cfg.marketdata_stale_seconds:missing.append(key)
                if missing:
                    try:await recover(await asyncio.to_thread(self.make_provider),missing,self.store,self.owner)
                    except Exception:pass
    async def run_leader(self):
        await asyncio.to_thread(self.initialize)
        worker=self
        class LazyProvider:
            def __init__(self):self.inner=None
            @property
            def socket(self):return self.inner.socket
            async def connect(self):self.inner=await asyncio.to_thread(worker.make_provider);await self.inner.connect()
            async def disconnect(self):
                if self.inner:await self.inner.disconnect()
            async def subscribe(self,keys,mode):await self.inner.subscribe(keys,mode)
            async def unsubscribe(self,keys):await self.inner.unsubscribe(keys)
        manager=FeedManager(LazyProvider(),self.store,self.owner,self.desired,lambda:self.enabled(True) and cfg.marketdata_distribution_approved,self.consume,self.persist_status)
        tasks=[asyncio.create_task(task) for task in (self.renew(),manager.run(),self.jobs(),self.snapshots())]
        try:
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_EXCEPTION)
            for task in done:task.result()
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            await asyncio.to_thread(self.store.release,self.owner)

async def main():
    # Import all ORM tables before validating the deployment schema.
    from app import main as application
    with engine.connect() as connection:check_schema(connection)
    while True:
        worker=MarketWorker()
        try:
            if await asyncio.to_thread(worker.store.acquire,worker.owner):await worker.run_leader()
            else:await asyncio.sleep(5)
        except asyncio.CancelledError:raise
        except Exception:
            # No exception repr/URL/token is written to worker logs.
            print('Market-data worker unavailable; retrying controlled ownership.',flush=True)
            await asyncio.sleep(5)
if __name__=='__main__':asyncio.run(main())
