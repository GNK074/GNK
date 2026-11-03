"""Bounded Redis state, provider-wide throttles, and fenced single-leader writes."""
import hashlib,json,time
from app.core.config import now
from app.market_data.config import market_settings as cfg
from app.market_data.providers.base import ProviderError
PREFIX='gnk:marketdata:'
LEASE=PREFIX+'leader'
TICK_LUA="""
if redis.call('GET',KEYS[1])~=ARGV[1] then return -3 end
local old=redis.call('GET',KEYS[2])
if old then
 local prior=cjson.decode(old)
 if tonumber(prior._order)>tonumber(ARGV[3]) or (prior._trade_order and tonumber(prior._trade_order)>tonumber(ARGV[8])) then return -1 end
 if prior._fingerprint==ARGV[4] then return 0 end
end
redis.call('SET',KEYS[2],ARGV[2],'EX',ARGV[5])
redis.call('XADD',KEYS[3],'MAXLEN','~',ARGV[6],'*','instrument_key',ARGV[7],'payload',ARGV[2])
return 1
"""
class RedisStore:
    def __init__(self,client):self.client=client
    def acquire(self,owner):return bool(self.client.set(LEASE,owner,nx=True,ex=cfg.marketdata_worker_lease_seconds))
    def owns(self,owner):
        value=self.client.get(LEASE)
        return bool(value and (value.decode() if isinstance(value,bytes) else value)==owner)
    def renew(self,owner):return bool(self.client.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('EXPIRE',KEYS[1],ARGV[2]) else return 0 end",1,LEASE,owner,cfg.marketdata_worker_lease_seconds))
    def release(self,owner):return self.client.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end",1,LEASE,owner)
    def provider_request_allowed(self):
        for seconds,maximum in ((1,5),(60,100),(1800,1500)):
            key=PREFIX+f'rate:{seconds}:{int(time.time())//seconds}'
            count=self.client.eval("local n=redis.call('INCR',KEYS[1]);if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end;return n",1,key,seconds+1)
            if count>maximum:return False
        return True
    def user_allowed(self,user_id,maximum=120):
        key=PREFIX+f'user-rate:{user_id}:{int(time.time())//60}'
        n=self.client.eval("local n=redis.call('INCR',KEYS[1]);if n==1 then redis.call('EXPIRE',KEYS[1],60) end;return n",1,key)
        return n<=maximum
    def put_tick(self,tick,owner):
        raw=dict(tick)
        stamp=raw.get('provider_timestamp') or raw.get('ltt')
        if not stamp:return -2
        from datetime import datetime
        raw['_order']=int(datetime.fromisoformat(stamp).timestamp()*1000)
        raw['_trade_order']=int(datetime.fromisoformat(raw['ltt']).timestamp()*1000) if raw.get('ltt') else 0
        semantic={k:v for k,v in raw.items() if k not in ('received_at','provider_timestamp','data_status','_order')}
        raw['_fingerprint']=hashlib.sha256(json.dumps(semantic,sort_keys=True).encode()).hexdigest()
        return self.client.eval(TICK_LUA,3,LEASE,self.tick_key(raw['instrument_key']),PREFIX+'events',owner,json.dumps(raw),raw['_order'],raw['_fingerprint'],cfg.marketdata_cache_seconds,cfg.marketdata_stream_maxlen,raw['instrument_key'],raw['_trade_order'])
    @staticmethod
    def tick_key(key):return PREFIX+'latest:'+hashlib.sha256(key.encode()).hexdigest()
    def latest(self,key):
        data=self.client.get(self.tick_key(key))
        if not data:return None
        value=json.loads(data)
        return {k:v for k,v in value.items() if not k.startswith('_')}
    def set_state(self,owner,state):
        state={**state,'updated_at':now().isoformat()}
        return self.client.eval("if redis.call('GET',KEYS[1])~=ARGV[1] then return 0 end;redis.call('SET',KEYS[2],ARGV[2],'EX',ARGV[3]);return 1",2,LEASE,PREFIX+'state',owner,json.dumps(state),cfg.marketdata_worker_lease_seconds)
    def state(self):
        raw=self.client.get(PREFIX+'state');return json.loads(raw) if raw else {'state':'DISCONNECTED','segments':{}}
    def ticket(self,token_hash,payload):self.client.set(PREFIX+'ticket:'+token_hash,json.dumps(payload),ex=30,nx=True)
    def consume_ticket(self,token_hash):
        raw=self.client.getdel(PREFIX+'ticket:'+token_hash)
        return json.loads(raw) if raw else None
    def last_event_id(self):
        rows=self.client.xrevrange(PREFIX+'events',count=1)
        return rows[0][0] if rows else '0-0'
    def events(self,last_id):return self.client.xread({PREFIX+'events':last_id},count=100,block=1000)

    def socket_slot(self,user_id,connection_id,release=False):
        key=PREFIX+'sockets:'+user_id
        if release:return self.client.zrem(key,connection_id)
        return bool(self.client.eval("redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',ARGV[1]);if not redis.call('ZSCORE',KEYS[1],ARGV[2]) and redis.call('ZCARD',KEYS[1])>=3 then return 0 end;redis.call('ZADD',KEYS[1],ARGV[3],ARGV[2]);redis.call('EXPIRE',KEYS[1],90);return 1",1,key,time.time(),connection_id,time.time()+60))
