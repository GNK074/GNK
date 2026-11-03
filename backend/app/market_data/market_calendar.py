import json
from datetime import datetime,time
from zoneinfo import ZoneInfo
from app.core.config import now
from app.market_data.config import market_settings as cfg
IST=ZoneInfo('Asia/Kolkata')

def market_session(segment,provider_info=None):
    local=now().astimezone(IST)
    info=provider_info or {}
    statuses=info.get('segments',{})
    if segment in statuses:
        return {'status':statuses[segment],'source':'UPSTOX_V3','timezone':'Asia/Kolkata','as_of':info.get('received_at')}
    special=json.loads(cfg.marketdata_special_sessions)
    date=local.date().isoformat()
    if date in special:
        start,end=special[date]
        opened=time.fromisoformat(start)<=local.time().replace(tzinfo=None)<=time.fromisoformat(end)
    else:
        opened=local.weekday()<5 and date not in cfg.marketdata_holidays.split(',') and time(9,15)<=local.time().replace(tzinfo=None)<=time(15,30)
    return {'status':'SCHEDULED_OPEN' if opened else 'SCHEDULED_CLOSED','source':'CONFIGURED_CALENDAR_NOT_EXCHANGE_CONFIRMATION','timezone':'Asia/Kolkata','as_of':now().isoformat()}

def quality(tick,connected=False,session=None):
    result=dict(tick)
    if tick.get('ltp') is None:result['data_status']='MISSING'
    elif not connected:result['data_status']='DISCONNECTED'
    elif (session or {}).get('status')!='NORMAL_OPEN':result['data_status']='MARKET_CLOSED' if (session or {}).get('status') in ('NORMAL_CLOSE','SCHEDULED_CLOSED','CLOSING_END') else 'UNVERIFIED_SESSION'
    else:
        stamps=[tick.get('ltt'),tick.get('provider_timestamp'),tick.get('received_at')]
        ages=[(now()-datetime.fromisoformat(x)).total_seconds() for x in stamps if x]
        result['data_status']='LIVE' if len(ages)==3 and all(-5<=x<=cfg.marketdata_stale_seconds for x in ages) else 'STALE'
    if tick.get('source')=='UPSTOX_REST' and result['data_status']=='LIVE':result['data_status']='SNAPSHOT'
    return result
