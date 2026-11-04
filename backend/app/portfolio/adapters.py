"""Allowlisted read-only broker transport. No arbitrary URL or trading method."""
from decimal import Decimal,InvalidOperation
import json,time,re
import httpx

KINDS=('holdings','positions','funds','orders','trades')
class PortfolioError(Exception):
    def __init__(self,code='BROKER_UNAVAILABLE'):self.code=code;super().__init__(code)

def number(v):
    if v is None or v=='':return None
    if isinstance(v,bool):raise PortfolioError('INVALID_RESPONSE')
    try:
        d=Decimal(str(v))
        if not d.is_finite() or abs(d)>Decimal('1e24'):raise ValueError()
        return d
    except (ValueError,InvalidOperation):raise PortfolioError('INVALID_RESPONSE') from None

def text(v):return str(v or '')[:160]
def pick(r,*keys):
    for k in keys:
        if k in r and r[k] is not None:return r[k]
    return None

def rows(value):
    if not isinstance(value,list) or len(value)>10000 or any(not isinstance(r,dict) for r in value):raise PortfolioError('INVALID_RESPONSE')
    return value

class Adapter:
    interval=1.1
    def __init__(self,credentials,account,transport=None,sleep=time.sleep):
        self.c=credentials;self.account=account;self.transport=transport;self.sleep=sleep
    def request(self,kind):
        method,url,headers,body=self.endpoint(kind)
        for attempt in range(2):
            # Strictly sequential, at most one read per second per account lease.
            self.sleep(self.interval)
            try:
                with httpx.Client(transport=self.transport,timeout=httpx.Timeout(12,connect=5),follow_redirects=False) as client:
                    with client.stream(method,url,headers=headers,json=body) as response:
                        if response.status_code==401:raise PortfolioError('SESSION_EXPIRED')
                        if response.status_code==403:raise PortfolioError('PERMISSION_DENIED')
                        if response.status_code==429:raise PortfolioError('RATE_LIMITED')
                        if response.status_code>=500:raise PortfolioError('BROKER_UNAVAILABLE')
                        if response.status_code!=200:raise PortfolioError('INVALID_RESPONSE')
                        data=bytearray()
                        for chunk in response.iter_bytes():
                            data.extend(chunk)
                            if len(data)>8_000_000:raise PortfolioError('RESPONSE_TOO_LARGE')
                return json.loads(data,parse_float=Decimal)
            except PortfolioError as e:
                if e.code!='BROKER_UNAVAILABLE' or attempt:raise
            except (httpx.TimeoutException,httpx.NetworkError):
                if attempt:raise PortfolioError() from None
            except (ValueError,TypeError):raise PortfolioError('INVALID_RESPONSE') from None
        raise PortfolioError()
    def fetch(self,kind):
        try:return normalize(self.name,kind,self.unwrap(kind,self.request(kind)))
        except (KeyError,TypeError,AttributeError):raise PortfolioError('INVALID_RESPONSE') from None

class Upstox(Adapter):
    name='upstox'
    paths={'holdings':'portfolio/long-term-holdings','positions':'portfolio/short-term-positions','funds':'user/get-funds-and-margin','orders':'order/retrieve-all','trades':'order/trades/get-trades-for-day'}
    def endpoint(self,k):return 'GET','https://api.upstox.com/v2/'+self.paths[k],{'Authorization':'Bearer '+self.c['access_token'],'Accept':'application/json'},None
    def unwrap(self,k,d):
        if d.get('status')!='success':raise PortfolioError('BROKER_REJECTED')
        return d['data']

class Zerodha(Adapter):
    name='zerodha'
    paths={'holdings':'portfolio/holdings','positions':'portfolio/positions','funds':'user/margins','orders':'orders','trades':'trades'}
    def endpoint(self,k):return 'GET','https://api.kite.trade/'+self.paths[k],{'Authorization':'token '+self.c['api_key']+':'+self.c['access_token'],'X-Kite-Version':'3'},None
    def unwrap(self,k,d):
        if d.get('status')!='success':raise PortfolioError('SESSION_EXPIRED' if d.get('error_type')=='TokenException' else 'BROKER_REJECTED')
        return d['data']['net'] if k=='positions' else d['data']

class Dhan(Adapter):
    name='dhan'
    paths={'holdings':'holdings','positions':'positions','funds':'fundlimit','orders':'orders','trades':'trades'}
    def endpoint(self,k):return 'GET','https://api.dhan.co/v2/'+self.paths[k],{'access-token':self.c['access_token'],'Accept':'application/json'},None
    def unwrap(self,k,d):
        if isinstance(d,dict) and d.get('errorCode'):raise PortfolioError('BROKER_REJECTED')
        return d

class Fyers(Adapter):
    name='fyers'
    paths={'holdings':'holdings','positions':'positions','funds':'funds','orders':'orders','trades':'tradebook'}
    keys={'holdings':'holdings','positions':'netPositions','funds':'fund_limit','orders':'orderBook','trades':'tradeBook'}
    def endpoint(self,k):return 'GET','https://api-t1.fyers.in/api/v3/'+self.paths[k],{'Authorization':self.c['app_id']+':'+self.c['access_token']},None
    def unwrap(self,k,d):
        if d.get('s')!='ok':raise PortfolioError('SESSION_EXPIRED' if d.get('code') in (-8,-9,-16) else 'BROKER_REJECTED')
        return d[self.keys[k]]

class Angel(Adapter):
    name='angelone'
    paths={'holdings':'portfolio/v1/getHolding','positions':'order/v1/getPosition','funds':'user/v1/getRMS','orders':'order/v1/getOrderBook','trades':'order/v1/getTradeBook'}
    def endpoint(self,k):
        from app.core.config import settings
        import socket,uuid,ipaddress
        if not settings.broker_egress_ip:raise PortfolioError('EGRESS_IP_REQUIRED')
        ip=str(ipaddress.ip_address(settings.broker_egress_ip))
        headers={'Authorization':'Bearer '+self.c['jwt_token'],'X-PrivateKey':self.c['api_key'],'X-UserType':'USER','X-SourceID':'WEB','X-ClientLocalIP':socket.gethostbyname(socket.gethostname()),'X-ClientPublicIP':ip,'X-MACAddress':':'.join(f'{uuid.getnode():012x}'[i:i+2] for i in range(0,12,2))}
        return 'GET','https://apiconnect.angelone.in/rest/secure/angelbroking/'+self.paths[k],headers,None
    def unwrap(self,k,d):
        if d.get('status') is not True:raise PortfolioError('SESSION_EXPIRED' if d.get('errorcode') in ('AG8001','AG8002','AG8003') else 'BROKER_REJECTED')
        # Documented no-data success may be null for book endpoints only.
        return [] if d.get('data') is None and k in ('orders','trades') else d['data']

class FivePaisa(Adapter):
    name='5paisa'
    paths={'holdings':'V3/Holding','positions':'V3/NetPositionNetWise','funds':'V4/Margin','orders':'V4/OrderBook','trades':'V1/TradeBook'}
    keys={'holdings':'Data','positions':'NetPositionDetail','funds':'EquityMargin','orders':'OrderBookDetail','trades':'TradeBookDetail'}
    def endpoint(self,k):
        return 'POST','https://Openapi.5paisa.com/VendorsAPI/Service1.svc/'+self.paths[k],{'Authorization':'Bearer '+self.c['access_token'],'Content-Type':'application/json'},{'head':{'key':self.c['app_key']},'body':{'ClientCode':self.account}}
    def unwrap(self,k,d):
        b=d.get('body',{});status=b.get('Status')
        if str(d.get('head',{}).get('status',d.get('head',{}).get('Status')))!='0':raise PortfolioError('BROKER_REJECTED')
        if status==9:raise PortfolioError('SESSION_EXPIRED')
        if status==1 and b.get('Message','').lower().startswith(('no orders','no trade','no data','no record')) and k!='funds':return []
        if status!=0:raise PortfolioError('BROKER_REJECTED')
        return b[self.keys[k]]

ADAPTERS={a.name:a for a in (Upstox,Dhan,Zerodha,Angel,Fyers,FivePaisa)}

# Canonical values remain Decimal until JSON persistence; missing means unknown.
def normalize(broker,kind,data):
    if kind=='funds':return funds(broker,data)
    result=[]
    for i,r in enumerate(rows(data)):
        if r.get('currency') and r['currency']!='INR':raise PortfolioError('UNSUPPORTED_CURRENCY')
        symbol=text(pick(r,'trading_symbol','tradingsymbol','tradingSymbol','symbol','Symbol','ScripName'))
        if not symbol:raise PortfolioError('INVALID_RESPONSE')
        exchange=text(pick(r,'exchange','exchangeSegment','Exch'))
        if broker=='fyers':exchange=symbol.partition(':')[0] if ':' in symbol else exchange
        if broker=='5paisa':exchange={'N':'NSE','B':'BSE','M':'MCX'}.get(exchange,exchange)
        isin=text(pick(r,'isin','ISIN')).upper()
        if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]',isin):isin=''
        # Broker instrument IDs are namespaced, never cross-broker symbol matches.
        instrument=text(pick(r,'instrument_token','instrument_key','securityId','symboltoken','fytoken','fyToken','ScripCode','NseCode','BseCode'))
        product=text(pick(r,'product','productType','producttype','OrderFor','DelvIntra')) or ('DELIVERY' if kind=='holdings' else 'UNKNOWN')
        asset=text(pick(r,'instrument_type','instrumenttype','InstrumentType')).upper() or 'UNKNOWN'
        if asset in ('EQ','EQUITY'):asset='EQUITY'
        if kind=='holdings' and broker=='fyers' and r.get('holdingType')=='MF':asset='MUTUAL_FUND'
        out=dict(row_key=str(i),symbol=symbol,exchange=exchange,product=product,currency='INR',asset_class=asset,isin=isin or None,instrument_id=instrument or None,price_status='BROKER_SNAPSHOT')
        if kind=='holdings':
            quantity=number(pick(r,'quantity','totalQty','Quantity','Qty','NetQty'))
            # Kite quantity excludes T1. FYERS reports current remainingQuantity.
            if broker=='zerodha':quantity=None if quantity is None or r.get('t1_quantity') is None else quantity+number(r['t1_quantity'])
            if broker=='fyers':quantity=number(r.get('remainingQuantity'))
            avg=number(pick(r,'average_price','avgCostPrice','averageprice','costPrice','AvgRate'))
            price=number(pick(r,'last_price','lastPrice','ltp','LTP','CurrentPrice'))
            if quantity is None or quantity<0:raise PortfolioError('INVALID_RESPONSE')
            invested=quantity*avg if avg is not None else None
            current=quantity*price if price is not None else None
            pnl=current-invested if current is not None and invested is not None else None
            out.update(quantity=quantity,average_cost=avg,current_price=price,invested_value=invested,current_value=current,pnl=pnl,pnl_percent=pnl/invested*100 if pnl is not None and invested else None)
        elif kind=='positions':
            qty=number(pick(r,'quantity','netQty','netqty','NetQty'))
            if qty is None:raise PortfolioError('INVALID_RESPONSE')
            out.update(net_quantity=qty,buy_quantity=number(pick(r,'buy_quantity','dayBuyQty','buyQty','buyqty','BuyQty')),sell_quantity=number(pick(r,'sell_quantity','daySellQty','sellQty','sellqty','SellQty')),average_price=number(pick(r,'average_price','costPrice','netAvg','avgnetprice','NetRate')),current_price=number(pick(r,'last_price','lastPrice','ltp','LTP','CurrentPrice')),realized_pnl=number(pick(r,'realised','realized_profit','realizedProfit','realisedprofit','BookedPL')),unrealized_pnl=number(pick(r,'unrealised','unrealized_profit','unrealizedProfit','unrealisedprofit')))
            # Angel spells realised/unrealised differently; do not use total pnl as both.
            if broker=='angelone':
                out['realized_pnl']=number(pick(r,'realised','realisedprofit'));out['unrealized_pnl']=number(pick(r,'unrealised','unrealisedprofit'))
            total=number(pick(r,'pnl','pl','PnL'))
            if total is None and out['realized_pnl'] is not None and out['unrealized_pnl'] is not None:total=out['realized_pnl']+out['unrealized_pnl']
            out['total_pnl']=total
        else:
            oid=pick(r,'order_id','orderId','orderid','id','BrokerOrderId','OrderID','ExchOrderID')
            tid=pick(r,'trade_id','tradeId','tradeid','TradeID','ExchTradeID','ExchangeTradeID')
            out.update(order_id=text(oid),trade_id=text(tid) if kind=='trades' else None,status=text(pick(r,'status','orderStatus','OrderStatus')),side=text(pick(r,'transaction_type','transactionType','transactiontype','side','BuySell')),quantity=number(pick(r,'quantity','qty','Qty','TradedQty')),price=number(pick(r,'average_price','price','tradePrice','fillprice','TradeRate','Rate')),broker_time=text(pick(r,'order_timestamp','exchange_timestamp','orderDateTime','exchtime','orderEntryTime','OrderDateTime','TradeDate','ExchangeTradeTime')))
        result.append(out)
    return result

def funds(b,d):
    def row(segment,available=None,used=None,collateral=None,cash=None):return dict(segment=segment,currency='INR',available=number(available),used_margin=number(used),collateral=number(collateral),cash=number(cash))
    if b=='upstox':
        if not isinstance(d,dict) or not d:raise PortfolioError('INVALID_RESPONSE')
        return [row(k,v.get('available_margin'),v.get('used_margin')) for k,v in d.items() if isinstance(v,dict)]
    if b=='zerodha':
        if not isinstance(d,dict) or not d:raise PortfolioError('INVALID_RESPONSE')
        return [row(k,v.get('net'),v.get('utilised',{}).get('debits'),v.get('available',{}).get('collateral'),v.get('available',{}).get('cash')) for k,v in d.items()]
    if b=='dhan':return [row('ALL',d.get('availabelBalance'),d.get('utilizedAmount'),d.get('collateralAmount'),d.get('sodLimit'))]
    if b=='angelone':return [row('ALL',d.get('net'),d.get('utiliseddebits'),d.get('collateral'),d.get('availablecash'))]
    if b=='fyers':
        data=rows(d);available=next((v for v in data if v.get('title')=='Available Balance'),None)
        if available is None:raise PortfolioError('INVALID_RESPONSE')
        used=next((v for v in data if v.get('title')=='Utilized Amount'),{})
        return [row(k,available.get(f),used.get(f)) for k,f in [('CAPITAL','equityAmount'),('COMMODITY','commodityAmount')]]
    if b=='5paisa':
        data=rows(d) if isinstance(d,list) else [d]
        return [row(text(v.get('Exch','EQUITY')),pick(v,'NetAvailableMargin','AvailableMargin'),v.get('MarginUtilized'),v.get('CollateralValueAfterHairCut'),v.get('Ledgerbalance')) for v in data]
    raise PortfolioError('UNSUPPORTED')
