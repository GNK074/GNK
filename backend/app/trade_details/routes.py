from datetime import timezone
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter,Depends,Query,HTTPException
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
from app.market_data.models import MarketInstrument
from app.market_data.subscription_manager import available_instrument
from app.services.accounts import audit
from .models import TradeSignal
router=APIRouter(prefix='/api/v1/tradedetails')

def json(value,status=200):return JSONResponse(jsonable_encoder(value,custom_encoder={Decimal:str}),status_code=status)

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
    return {'id':row.id,'signal_time':(row.signal_time.astimezone(timezone.utc) if row.signal_time.tzinfo else row.signal_time.replace(tzinfo=timezone.utc)),'symbol':row.symbol,'strike_price':row.strike_price,'order_type':row.order_type,'side':row.side,'quantity':row.quantity,'reference_price':row.reference_price,'strategy_id':row.strategy_id,'group_service':strategy.name if strategy else None,'account_id':row.account_id,'source':row.source,'source_order_id':row.source_order_id,'note':row.note,'execution':'SIGNAL_ONLY_NO_ORDER_SUBMITTED' if row.source=='MANUAL' else 'RECORDED_ORDER_REQUEST_NOT_A_FILL'}

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
