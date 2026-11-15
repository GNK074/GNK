"""Dhan SDK adapter for the existing GNK durable LIMIT execution workflow."""
from decimal import Decimal
from app.core.config import settings
from app.execution.upstox import ExecutionError,decimal,integer
from .client import DhanClient,DhanError
from .instruments import key
from . import streams
class DhanExecution:
    def __init__(self,client_id,token,account_id,user_id,transport=None,credential_version=""):
        self.client=DhanClient(client_id,token,transport,execution=True);self.account_id=account_id;self.user_id=user_id;self.credential_version=credential_version
    def call(self,fn):
        try:return fn()
        except DhanError as e:raise ExecutionError(e.code,e.ambiguous) from None
    def verify_identity(self,expected):
        d=self.call(self.client.profile)
        if not isinstance(d,dict) or str(d.get('dhanClientId'))!=expected:raise ExecutionError('BROKER_IDENTITY_MISMATCH')
        ips=self.call(lambda:self.client.unwrap(self.client.context.dhan_http.get('/ip/getIP')))
        if not isinstance(ips,dict) or settings.broker_egress_ip not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise ExecutionError('REGISTERED_EGRESS_IP_MISMATCH')
    def list(self,value):
        if not isinstance(value,list) or len(value)>10000 or any(not isinstance(r,dict) for r in value):raise ExecutionError('INVALID_BROKER_SNAPSHOT')
        return value
    def book(self):
        result=[]
        statuses={'TRANSIT':'validation pending','PENDING':'open','PART_TRADED':'open','TRADED':'complete','CANCELLED':'cancelled','REJECTED':'rejected','EXPIRED':'cancelled'}
        for r in self.list(self.call(lambda:self.client.read('orders'))):
            result.append(dict(order_id=str(r.get('orderId','')),tag=r.get('correlationId'),instrument_token=key(r.get('exchangeSegment',''),str(r.get('securityId',''))),transaction_type=r.get('transactionType'),quantity=integer(r.get('quantity')),filled_quantity=integer(r.get('filledQty')),price=decimal(r.get('price')),product='I' if r.get('productType')=='INTRADAY' else str(r.get('productType','')),order_type=r.get('orderType'),status=statuses.get(r.get('orderStatus'),'unknown')))
        return result
    def positions(self):
        result=[]
        fingerprint=self.credential_version
        for r in self.list(self.call(lambda:self.client.read('positions'))):
            instrument=key(r.get('exchangeSegment',''),str(r.get('securityId','')));qty=integer(r.get('netQty'))
            price=r.get('lastPrice')
            if qty and price is None:
                quote=streams.latest(self.user_id,self.account_id,fingerprint,instrument)
                if quote.get('data_status')!='LIVE':raise ExecutionError('POSITION_EXPOSURE_PRICE_UNAVAILABLE')
                price=quote['ltp']
            result.append(dict(instrument_token=instrument,trading_symbol=r.get('tradingSymbol'),product='I' if r.get('productType')=='INTRADAY' else str(r.get('productType','')),quantity=qty,last_price=decimal(price if qty else 0),average_price=decimal(r.get('costPrice')),realised=decimal(r.get('realizedProfit')),unrealised=decimal(r.get('unrealizedProfit'))))
        return result
    def trades(self,order_id):
        values=self.call(lambda:self.client.unwrap(self.client.sdk.get_trade_book(order_id)))
        return [dict(order_id=str(r.get('orderId','')),trade_id=str(r.get('exchangeTradeId','')),transaction_type=r.get('transactionType'),product='I' if r.get('productType')=='INTRADAY' else str(r.get('productType','')),quantity=integer(r.get('tradedQuantity')),average_price=decimal(r.get('tradedPrice')),exchange_timestamp=r.get('exchangeTime','')) for r in self.list(values)]
    def place(self,row):
        _,segment,sid=row.instrument_key.split('|')
        value=self.call(lambda:self.client.unwrap(self.client.sdk.place_order(sid,segment,row.side,row.quantity,'LIMIT','INTRADAY',float(row.price),validity='DAY',tag=row.tag)))
        if not isinstance(value,dict) or not isinstance(value.get('orderId'),str) or not value['orderId']:raise ExecutionError('SUBMISSION_REQUIRES_RECONCILIATION',True)
        return value['orderId']
    def cancel(self,order_id):
        value=self.call(lambda:self.client.unwrap(self.client.sdk.cancel_order(order_id)))
        if not isinstance(value,dict) or str(value.get('orderId'))!=order_id:raise ExecutionError('CANCEL_REQUIRES_RECONCILIATION',True)
        return value
