"""Ticket-authenticated GNK sockets; only user-owned subscriptions are routed."""
import asyncio,json,time,uuid
import anyio
from fastapi import APIRouter,WebSocket,WebSocketDisconnect,HTTPException
from sqlalchemy import select
from app.core.config import settings,digest,expired
from app.database.session import DB
from app.database.tenancy import set_context
from app.models.identity import User,LoginSession
from app.market_data.models import MarketSubscription
from app.market_data.service import get_store,MarketDataService,filter_mode
from app.market_data.schemas import SubscribeInput
from app.market_data.subscription_manager import entitlement,subscribe
from app.market_data.providers.base import ProviderError
router=APIRouter()

def socket_identity(proof):
    if time.time()>=proof['access_expires']:raise HTTPException(401,'Session expired')
    with DB() as s:
        user=s.get(User,proof['user_id']);session=s.get(LoginSession,proof['session_id'])
        if not user or not session or session.user_id!=user.id or session.revoked or expired(session.expires) or not session.mfa_complete or not user.active or not user.verified:raise HTTPException(401,'Session unavailable')
        set_context(s,user.id);entitlement(s,user.id)
    return proof['user_id']

@router.websocket('/ws/v1/marketdata')
async def market_socket(ws:WebSocket):
    store=get_store();proof=None;tasks=[];connection_id=uuid.uuid4().hex
    try:
        if ws.headers.get('origin','').rstrip('/') not in {x.rstrip('/') for x in settings.origins}:raise ValueError()
        protocols=[p.strip() for p in ws.headers.get('sec-websocket-protocol','').split(',')]
        if len(protocols)!=2 or protocols[0]!='gnk.marketdata' or len(protocols[1])>100:raise ValueError()
        proof=await asyncio.to_thread(store.consume_ticket,digest(protocols[1]))
        if not proof:raise ValueError()
        uid=await asyncio.to_thread(socket_identity,proof)
        if not await asyncio.to_thread(store.socket_slot,uid,connection_id):raise ValueError()
    except Exception:
        await ws.close(code=1008);return
    await ws.accept(subprotocol='gnk.marketdata')
    selected={};cursor=await asyncio.to_thread(store.last_event_id)
    send_lock=asyncio.Lock()
    async def send(value):
        async with send_lock:await asyncio.wait_for(ws.send_json(value),timeout=3)
    async def snapshots(keys):
        def read():
            with DB() as s:
                set_context(s,uid)
                result=[]
                service=MarketDataService(s,uid,store)
                for key in keys:result.extend(service.quotes([key],selected[key]))
                return result
        for tick in await asyncio.to_thread(read):await send({'type':'market_tick',**tick,'status':tick['data_status']})
    async def receive():
        while True:
            raw=await ws.receive_text()
            if len(raw)>32768:raise ValueError()
            if not await asyncio.to_thread(store.user_allowed,uid,240):raise ValueError()
            try:
                message=json.loads(raw);action=message.get('action')
                if action=='PING':await send({'type':'PONG'});continue
                if action=='PONG':continue
                if action not in ('SUBSCRIBE','UNSUBSCRIBE','CHANGE_MODE'):raise ValueError()
                if set(message)-{'action','instrument_keys','mode'}:raise ValueError()
                data=SubscribeInput(instrument_keys=message.get('instrument_keys'),mode=message.get('mode','ltpc'))
                if action=='CHANGE_MODE' and not set(data.instrument_keys)<=set(selected):raise ValueError()
                await asyncio.to_thread(socket_identity,proof)
                def change():
                    with DB() as s:
                        set_context(s,uid)
                        if action=='UNSUBSCRIBE':
                            rows=list(s.scalars(select(MarketSubscription).where(MarketSubscription.user_id==uid,MarketSubscription.instrument_key.in_(data.instrument_keys))))
                            for row in rows:s.delete(row)
                        else:subscribe(s,uid,data.instrument_keys,data.mode)
                        s.commit()
                await asyncio.to_thread(change)
                for key in data.instrument_keys:
                    if action=='UNSUBSCRIBE':selected.pop(key,None)
                    else:selected[key]=data.mode
                await send({'type':'subscription_ack','action':action,'instrument_keys':data.instrument_keys,'mode':data.mode})
                if action!='UNSUBSCRIBE':await snapshots(data.instrument_keys)
            except (HTTPException,ValueError,ProviderError) as error:
                code=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,str) else 'INVALID_MARKET_SUBSCRIPTION'
                await send({'type':'error','message':code})
    async def events():
        nonlocal cursor
        from app.market_data.market_calendar import quality,market_session
        from app.market_data.models import MarketInstrument
        while True:
            await asyncio.to_thread(socket_identity,proof)
            if not await asyncio.to_thread(store.socket_slot,uid,connection_id):raise ValueError()
            rows=await asyncio.to_thread(store.events,cursor)
            state=await asyncio.to_thread(store.state)
            if not rows:
                await send({'type':'feed_status','state':state.get('state','DISCONNECTED')});continue
            for _,entries in rows:
                for event_id,fields in entries:
                    cursor=event_id
                    if isinstance(event_id,bytes):event_id=event_id.decode()
                    if time.time()*1000-int(event_id.split('-')[0])>5000:
                        cursor=await asyncio.to_thread(store.last_event_id)
                        await send({'type':'resync_required','reason':'Slow consumer; fresh snapshots follow.'})
                        if selected:await snapshots(list(selected))
                        break
                    raw=fields.get(b'payload',fields.get('payload'));tick=json.loads(raw)
                    key=tick['instrument_key']
                    if key not in selected:continue
                    def read_tick():
                        with DB() as s:
                            set_context(s,uid)
                            from app.market_data.subscription_manager import available_instrument,provider_status
                            instrument=available_instrument(s,uid,key,selected[key])
                            row=provider_status(s)
                            from app.market_data.config import market_settings as cfg
                            return filter_mode(quality(tick,cfg.upstox_enabled and row.enabled and state.get('state')=='CONNECTED',market_session(instrument.segment,{'segments':state.get('segments',{}),'received_at':state.get('updated_at')})),selected[key])
                    value=await asyncio.to_thread(read_tick)
                    await send({'type':'market_tick',**value,'status':value['data_status']})
    tasks=[asyncio.create_task(receive()),asyncio.create_task(events())]
    try:
        done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for task in done:task.result()
    except (Exception,asyncio.CancelledError):pass
    finally:
        # ASGI shutdown may cancel repeatedly; shield cleanup so socket slots and
        # child tasks are released even when the client disconnects immediately.
        with anyio.CancelScope(shield=True):
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            await asyncio.to_thread(store.socket_slot,uid,connection_id,True)
            try:await ws.close(code=1000)
            except Exception:pass
