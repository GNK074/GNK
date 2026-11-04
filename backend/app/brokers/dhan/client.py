"""Official DhanHQ SDK with a bounded, secret-safe transport boundary.

SDK business methods build payloads; this transport prevents redirects,
unbounded requests, raw SDK exception logging and accidental order writes.
"""
import json,re,time,hashlib
from decimal import Decimal
import httpx
from dhanhq import DhanContext,DhanHTTP,dhanhq
from app.security.authentication import cache

SDK_VERSION='2.3.0'
READS={('GET','/holdings'),('GET','/positions'),('GET','/fundlimit'),('GET','/orders'),('GET','/trades'),('GET','/trades/'),('GET','/profile'),('GET','/RenewToken'),('POST','/marketfeed/ltp'),('POST','/marketfeed/ohlc'),('POST','/marketfeed/quote'),('POST','/optionchain'),('POST','/optionchain/expirylist'),('POST','/charts/intraday'),('POST','/charts/historical'),('POST','/charts/rollingoption'),('POST','/margincalculator'),('POST','/margincalculator/multi')}
class DhanError(Exception):
    def __init__(self,code='DHAN_UNAVAILABLE'):self.code=code;super().__init__(code)

def guard(client_id):
    subject=hashlib.sha256(client_id.encode()).hexdigest()
    try:
        # Shared across processes; one customer's worker/UI cannot multiply limits.
        for period,maximum in ((1,4),(60,100)):
            key=f'gnk:dhan:rate:{subject}:{period}:{int(time.time())//period}'
            n=cache.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end return n",1,key,period+1)
            if n>maximum:raise DhanError('RATE_LIMITED')
    except DhanError:raise
    except Exception:raise DhanError('CACHE_UNAVAILABLE') from None

class SafeDhanHTTP(DhanHTTP):
    def __init__(self,client_id,token,transport=None):
        super().__init__(client_id,token)
        self.transport=transport
        self.header['dhanClientId']=client_id
        # No requests from the SDK's unguarded default session are needed.
        self.session.close()
    def _send_request(self,method,endpoint,payload=None):
        verb=method.value
        if endpoint=='/trades/':endpoint='/trades'
        allowed=(verb,endpoint) in READS or (verb=='GET' and bool(re.fullmatch(r'/orders/[A-Za-z0-9_-]{1,100}|/trades/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}/\d{1,3}',endpoint)))
        if not allowed:raise DhanError('DHAN_OPERATION_NOT_ENABLED')
        if self.transport is None:guard(self.client_id)
        if payload is not None:
            payload=dict(payload)
            # SDK market requests use segment maps: adding dhanClientId would
            # turn it into an invalid segment. Header already identifies owner.
            if not endpoint.startswith('/marketfeed/'):payload['dhanClientId']=self.client_id
        try:
            with httpx.Client(transport=self.transport,timeout=httpx.Timeout(12,connect=5),follow_redirects=False,trust_env=False) as client:
                with client.stream(verb,self.base_url+endpoint,headers=self.header,json=payload) as response:
                    if response.status_code==401:raise DhanError('SESSION_EXPIRED')
                    if response.status_code==403:raise DhanError('PERMISSION_DENIED')
                    if response.status_code==429:raise DhanError('RATE_LIMITED')
                    if response.status_code>=500:raise DhanError('DHAN_UNAVAILABLE')
                    if response.status_code!=200:raise DhanError('DHAN_REQUEST_REJECTED')
                    data=bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data)>8_000_000:raise DhanError('DHAN_RESPONSE_TOO_LARGE')
            value=json.loads(data,parse_float=Decimal)
            if isinstance(value,dict) and value.get('errorCode'):raise DhanError('DHAN_REQUEST_REJECTED')
            return {'status':'success','remarks':'','data':value}
        except DhanError:raise
        except httpx.HTTPError:raise DhanError('DHAN_UNAVAILABLE') from None
        except (ValueError,TypeError):raise DhanError('INVALID_DHAN_RESPONSE') from None

class DhanClient:
    READ_METHODS={'holdings':'get_holdings','positions':'get_positions','funds':'get_fund_limits','orders':'get_order_list','trades':'get_trade_book'}
    def __init__(self,client_id,token,transport=None):
        if not isinstance(client_id,str) or not client_id.strip() or not isinstance(token,str) or not token:raise DhanError('DHAN_CREDENTIALS_UNAVAILABLE')
        self.context=DhanContext(client_id,token)
        self.context.dhan_http.session.close()
        self.context.dhan_http=SafeDhanHTTP(client_id,token,transport)
        self.sdk=dhanhq(self.context)
    def unwrap(self,result):
        if not isinstance(result,dict) or result.get('status')!='success' or 'data' not in result:raise DhanError('INVALID_DHAN_RESPONSE')
        return result['data']
    def read(self,kind):
        if kind not in self.READ_METHODS:raise DhanError('DHAN_OPERATION_NOT_ENABLED')
        return self.unwrap(getattr(self.sdk,self.READ_METHODS[kind])())
    def profile(self):return self.unwrap(self.context.dhan_http.get('/profile'))
    def renew(self):return self.unwrap(self.context.dhan_http.get('/RenewToken'))
    def market(self,result):
        value=self.unwrap(result)
        if not isinstance(value,dict) or value.get('status')!='success' or 'data' not in value:raise DhanError('INVALID_DHAN_RESPONSE')
        return value['data']
    def quote(self,securities,mode='ltp'):
        method={'ltp':self.sdk.ticker_data,'ohlc':self.sdk.ohlc_data,'full':self.sdk.quote_data}.get(mode)
        if not method:raise DhanError('INVALID_DHAN_MODE')
        return self.market(method(securities))
    def expiries(self,security_id,segment):return self.market(self.sdk.expiry_list(int(security_id),segment))
    def options(self,security_id,segment,expiry):return self.market(self.sdk.option_chain(int(security_id),segment,expiry))
    def history(self,security_id,segment,instrument,start,end,interval):
        if interval=='D':result=self.sdk.historical_daily_data(security_id,segment,instrument,start,end)
        else:result=self.sdk.intraday_minute_data(security_id,segment,instrument,start,end,interval=int(interval))
        return self.unwrap(result)
    def trade_history(self,start,end,page):return self.unwrap(self.sdk.get_trade_history(start,end,page_number=page))
