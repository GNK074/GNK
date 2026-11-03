"""Upstox trading credentials only. Mutations are never retried automatically."""
import httpx,time
from decimal import Decimal
from app.core.config import settings
from app.security.authentication import cache
class ExecutionError(RuntimeError):
    def __init__(self,code,ambiguous=False):super().__init__(code);self.code=code;self.ambiguous=ambiguous
class UpstoxExecution:
    def __init__(self,token,account_id,transport=None):self._token=token;self.account_id=account_id;self.transport=transport
    def request(self,method,path,**kwargs):
        allowed={('GET','/v2/user/profile'),('GET','/v2/order/retrieve-all'),('GET','/v2/order/trades'),('GET','/v2/portfolio/short-term-positions'),('POST','/v3/order/place'),('DELETE','/v3/order/cancel')}
        if (method,path) not in allowed:raise ExecutionError('EXECUTION_ENDPOINT_NOT_ALLOWED')
        for seconds,maximum in ((1,5),(60,80),(1800,1000)):
            key=f'gnk:execution:rate:{self.account_id}:{seconds}:{int(time.time())//seconds}'
            try:n=cache.eval("local n=redis.call('INCR',KEYS[1]);if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end;return n",1,key,seconds+1)
            except Exception:raise ExecutionError('EXECUTION_CACHE_UNAVAILABLE') from None
            if n>maximum:raise ExecutionError('EXECUTION_RATE_LIMIT')
        headers={'Authorization':'Bearer '+self._token,'Accept':'application/json'}
        if method=='POST' and settings.upstox_algo_name:headers['X-Algo-Name']=settings.upstox_algo_name
        base='https://api-hft.upstox.com' if method!='GET' else 'https://api.upstox.com'
        try:
            with httpx.Client(timeout=8,transport=self.transport,follow_redirects=False,trust_env=False) as client:r=client.request(method,base+path,headers=headers,**kwargs)
        except httpx.HTTPError:raise ExecutionError('BROKER_RESPONSE_UNKNOWN',method!='GET') from None
        if r.status_code in (401,403):raise ExecutionError('TRADING_TOKEN_REJECTED')
        if r.status_code>=500 or r.status_code==429:raise ExecutionError('BROKER_UNAVAILABLE',method!='GET')
        if r.status_code>=400:raise ExecutionError('BROKER_REQUEST_REJECTED')
        try:
            d=r.json()
            if not isinstance(d,dict) or d.get('status')!='success' or 'data' not in d:raise ValueError()
            return d['data']
        except (ValueError,TypeError):raise ExecutionError('INVALID_BROKER_RESPONSE',method!='GET') from None
    def verify_identity(self,expected):
        data=self.request('GET','/v2/user/profile')
        if not isinstance(data,dict) or data.get('is_active') is not True or data.get('user_id')!=expected:raise ExecutionError('BROKER_IDENTITY_MISMATCH')
    def book(self):
        data=self.request('GET','/v2/order/retrieve-all')
        if not isinstance(data,list) or len(data)>10000:raise ExecutionError('INVALID_ORDER_BOOK')
        return data
    def positions(self):
        data=self.request('GET','/v2/portfolio/short-term-positions')
        if not isinstance(data,list) or len(data)>10000:raise ExecutionError('INVALID_BROKER_POSITIONS')
        return data
    def trades(self,order_id):
        data=self.request('GET','/v2/order/trades',params={'order_id':order_id})
        if not isinstance(data,list) or len(data)>10000:raise ExecutionError('INVALID_BROKER_TRADES')
        return data
    def place(self,order):
        body={'quantity':order.quantity,'product':'I','validity':'DAY','price':float(order.price),'tag':order.tag,'instrument_token':order.instrument_key,'order_type':'LIMIT','transaction_type':order.side,'disclosed_quantity':0,'trigger_price':0,'is_amo':False,'slice':False}
        data=self.request('POST','/v3/order/place',json=body)
        ids=data.get('order_ids') if isinstance(data,dict) else None
        if not isinstance(ids,list) or len(ids)!=1 or not isinstance(ids[0],str) or not 1<=len(ids[0])<=100:raise ExecutionError('SUBMISSION_REQUIRES_RECONCILIATION',True)
        return ids[0]
    def cancel(self,order_id):
        data=self.request('DELETE','/v3/order/cancel',params={'order_id':order_id})
        if not isinstance(data,dict) or data.get('order_id')!=order_id:raise ExecutionError('CANCEL_REQUIRES_RECONCILIATION',True)
        return data

def decimal(value):
    try:
        if isinstance(value,bool):raise ValueError()
        result=Decimal(str(value))
        if not result.is_finite():raise ValueError()
        return result
    except Exception:raise ExecutionError('INVALID_BROKER_NUMBER') from None

def integer(value):
    result=decimal(value)
    if result!=int(result):raise ExecutionError('INVALID_BROKER_QUANTITY')
    return int(result)
