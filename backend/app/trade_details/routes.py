from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,Query,HTTPException,Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.database.session import db
from app.core.config import now
from app.security.authentication import auth
from app.security.ownership import owned
from app.models.trading import BrokerAccount,Strategy
from app.execution.models import LiveOrder
from app.execution.live_service import public as order_public
from app.market_data.models import MarketInstrument
from app.market_data.subscription_manager import available_instrument
from app.services.accounts import audit
from .models import TradeSignal
from .service import projections,filter_rows,paginate,metadata,ledger,running_summary
from .accounting import utc,IST
from .export import workbook
router=APIRouter(prefix='/api/v1/tradedetails')

def json(value,status=200):return JSONResponse(jsonable_encoder(value,custom_encoder={Decimal:str}),status_code=status)

class Filters:
    def __init__(self,broker:str=Query('',max_length=30),script:str=Query('',max_length=150),strategy_id:str=Query('',max_length=36),q:str=Query('',max_length=100),status:str=Query('',max_length=30),from_date:date|None=None,to_date:date|None=None):
        self.values=dict(broker=broker,script=script,strategy_id=strategy_id,q=q,status=status,from_date=from_date,to_date=to_date)

@router.get('/options')
def options(u=Depends(auth),s:Session=Depends(db)):
    accounts,strategies=metadata(s,u.id);orders=ledger(s,u.id)
    ids={o.instrument_id for o in orders}
    instruments=list(s.scalars(select(MarketInstrument).where(MarketInstrument.id.in_(ids)))) if ids else []
    scripts={x.underlying or x.symbol for x in instruments}|{'BANKNIFTY','NIFTY','MIDCPNIFTY','FINNIFTY','SENSEX'}
    return {'brokers':sorted({a.broker for a in accounts.values()}),'accounts':[{'id':a.id,'broker':a.broker,'status':a.status} for a in accounts.values()],'strategies':[{'id':x.id,'name':x.name} for x in strategies.values()],'scripts':sorted(scripts),'timezone':'Asia/Kolkata','execution_mode':'LIVE'}

@router.get('/orders')
def orders(filters:Filters=Depends(),bucket:Literal['ACTIVE','PENDING','CLOSED','FAILED','ALL']='ACTIVE',page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),sort:str='entry_time',direction:Literal['asc','desc']='desc',u=Depends(auth),s:Session=Depends(db)):
    rows,_,summary=projections(s,u)
    filtered=filter_rows(rows,**filters.values,bucket=bucket)
    context=filter_rows(rows,**filters.values)
    summary=running_summary(context)
    counts={key:sum(r['bucket']==key for r in context) for key in ('ACTIVE','PENDING','CLOSED','FAILED')}
    return json({**paginate(filtered,page,page_size,sort,direction),'summary':summary,'counts':counts,'scope':'OWN_RECORDED_LIVE_ORDERS','protective_orders':'SL and TP are unavailable; this table does not create protective orders.'})

@router.get('/client-trade-history/export')
def export_history(filters:Filters=Depends(),u=Depends(auth),s:Session=Depends(db)):
    _,rows,_=projections(s,u);rows=filter_rows(rows,**filters.values)
    rows.sort(key=lambda x:x.get('signal_entry_time') or x['signal_exit_time'],reverse=True)
    def ist(value):return value.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S IST') if value else ''
    headers=['S.No.','Signal Entry Time','Signal Exit Time','Trading Symbol','Group Service','Broker','Entry Qty','Exit Qty','Entry Price','Exit Price','Gross Realized P&L','Price','Price Status','Order Status','Trade Status','Response']
    values=[[i,ist(r['signal_entry_time']),ist(r['signal_exit_time']),r['trading_symbol'],r['group_service'],r['broker'],r['entry_qty'],r['exit_qty'],r['entry_price'],r['exit_price'],r['pnl'],r['price'],r['price_status'],r['order_status'],r['trade_status'],r['response']] for i,r in enumerate(rows,1)]
    return Response(workbook(headers,values),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="gnk-trade-history.xlsx"'})

@router.get('/client-trade-history')
def history(filters:Filters=Depends(),page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),sort:str='signal_entry_time',direction:Literal['asc','desc']='desc',u=Depends(auth),s:Session=Depends(db)):
    _,rows,summary=projections(s,u)
    filtered=filter_rows(rows,**filters.values);summary=running_summary(filtered,True)
    return json({**paginate(filtered,page,page_size,sort,direction),'summary':summary,'basis':'Gross FIFO from reconciled GNK fills only; fees and taxes excluded. Missing fill time or entry basis produces unknown P&L.'})

@router.get('/orders/{order_id}')
def detail(order_id:str,u=Depends(auth),s:Session=Depends(db)):
    row=owned(s,LiveOrder,order_id,u.id)
    orders,history,_=projections(s,u)
    return json({'order':order_public(row),'report':next(x for x in orders if x['id']==row.id),'trade_history':[x for x in history if x['id']==row.id or row.id in x['exit_order_ids']]})

class SignalInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    strategy_id:str
    account_id:str|None=None
    instrument_id:str
    side:Literal['BUY','SELL']
    order_type:Literal['LIMIT','MARKET','SL','SL-M']='LIMIT'
    quantity:int=Field(ge=1,le=100000)
    reference_price:Decimal|None=Field(default=None,gt=0,le=10000000,max_digits=24,decimal_places=8)
    note:str=Field(default='',max_length=500)

def signal_public(row,strategy=None):
    return {'id':row.id,'signal_time':utc(row.signal_time),'symbol':row.symbol,'strike_price':row.strike_price,'order_type':row.order_type,'side':row.side,'quantity':row.quantity,'reference_price':row.reference_price,'strategy_id':row.strategy_id,'group_service':strategy.name if strategy else None,'account_id':row.account_id,'source':row.source,'source_order_id':row.source_order_id,'note':row.note,'execution':'SIGNAL_ONLY_NO_ORDER_SUBMITTED' if row.source=='MANUAL' else 'RECORDED_ORDER_REQUEST_NOT_A_FILL'}

@router.get('/signals')
def signals(q:str=Query('',max_length=100),page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100),sort:Literal['signal_time','symbol','strike_price','order_type']='signal_time',direction:Literal['asc','desc']='desc',u=Depends(auth),s:Session=Depends(db)):
    statement=select(TradeSignal).where(TradeSignal.user_id==u.id)
    if q:
        term='%'+q.replace('%','').replace('_','')+'%'
        statement=statement.where(TradeSignal.symbol.ilike(term)|TradeSignal.side.ilike(term)|TradeSignal.order_type.ilike(term))
    total=s.scalar(select(func.count()).select_from(statement.subquery()))
    column=getattr(TradeSignal,sort);statement=statement.order_by(column.desc().nullslast() if direction=='desc' else column.asc().nullslast(),TradeSignal.id)
    rows=list(s.scalars(statement.offset((page-1)*page_size).limit(page_size)))
    return json({'items':[signal_public(x) for x in rows],'total':total,'page':page,'page_size':page_size,'pages':max(1,(total+page_size-1)//page_size)})

@router.get('/signals/{signal_id}')
def signal_detail(signal_id:str,u=Depends(auth),s:Session=Depends(db)):
    row=owned(s,TradeSignal,signal_id,u.id)
    strategy=s.scalar(select(Strategy).where(Strategy.id==row.strategy_id,Strategy.user_id==u.id))
    return json(signal_public(row,strategy))

@router.post('/signals',status_code=201)
def create_signal(data:SignalInput,u=Depends(auth),s:Session=Depends(db)):
    strategy=owned(s,Strategy,data.strategy_id,u.id)
    if data.account_id:owned(s,BrokerAccount,data.account_id,u.id)
    instrument=s.get(MarketInstrument,data.instrument_id)
    if not instrument:raise HTTPException(404,'Instrument not found')
    available_instrument(s,u.id,instrument.instrument_key,'ltpc')
    row=TradeSignal(user_id=u.id,strategy_id=strategy.id,account_id=data.account_id,instrument_id=instrument.id,symbol=instrument.symbol,strike_price=instrument.strike,side=data.side,order_type=data.order_type,quantity=data.quantity,reference_price=data.reference_price,note=data.note,source='MANUAL')
    s.add(row);s.flush();audit(s,u.id,'signal_created:'+row.id);s.commit()
    return json(signal_public(row,strategy),201)
