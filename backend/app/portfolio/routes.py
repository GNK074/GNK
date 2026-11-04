from typing import Literal
from fastapi import APIRouter,Depends,Query,HTTPException,Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database.session import db
from app.security.authentication import auth
from app.services.accounts import audit
from app.trade_details.export import workbook
from . import service as svc
router=APIRouter(prefix='/api/v1/portfolio',tags=['Portfolio'])
Kind=Literal['holdings','positions','funds','orders','trades']

def output(value):return JSONResponse(jsonable_encoder(svc.serialized(value)))
def filters(account_id:str|None=None,broker:str|None=Query(None,max_length=30),exchange:str|None=Query(None,max_length=30),product:str|None=Query(None,max_length=30),asset_class:str|None=Query(None,max_length=30),q:str|None=Query(None,max_length=100)):
    return dict(account_id=account_id,broker=broker,exchange=exchange,product=product,asset_class=asset_class,q=q)

@router.get('/summary')
def summary(f=Depends(filters),u=Depends(auth),s:Session=Depends(db)):return output(svc.summary(s,u.id,**f))

@router.get('/accounts')
@router.get('/sync-status')
def accounts(account_id:str|None=None,broker:str|None=None,u=Depends(auth),s:Session=Depends(db)):
    return output({'items':svc.public_accounts(s,u.id,account_id=account_id,broker=broker)})

class Refresh(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str|None=None

@router.post('/refresh',status_code=202)
def refresh(data:Refresh,u=Depends(auth),s:Session=Depends(db)):
    try:
        result=svc.queue(s,u.id,data.account_id);audit(s,u.id,'portfolio_refresh_requested');s.commit()
        return JSONResponse(result,status_code=202)
    except IntegrityError:
        s.rollback();raise HTTPException(409,'A portfolio refresh is already being queued') from None

@router.get('/{kind}/export')
def export(kind:Kind,f=Depends(filters),u=Depends(auth),s:Session=Depends(db)):
    items,coverage=svc.dataset(s,u.id,kind,**f)
    headers=['broker','account','symbol','exchange','product','currency','quantity','average_cost','current_price','invested_value','current_value','pnl','net_quantity','realized_pnl','unrealized_pnl','segment','available','used_margin','order_id','trade_id','status','source','price_status','fetched_at','instrument_id','order_type','trigger_price','filled_quantity','average_buy_price','average_sell_price','withdrawable']
    data=workbook(headers,[[r.get(k) for k in headers] for r in items])
    return Response(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="gnk-portfolio-{kind}.xlsx"'})

@router.get('/{kind}')
def data(kind:Kind,f=Depends(filters),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),sort:Literal['symbol','broker','exchange','product','quantity','pnl','current_value','net_quantity','total_pnl','available','broker_time']='symbol',direction:Literal['asc','desc']='asc',consolidated:bool=False,u=Depends(auth),s:Session=Depends(db)):
    items,coverage=svc.dataset(s,u.id,kind,**f)
    if consolidated and kind=='holdings':items=svc.consolidate(items,kind)
    numeric={'quantity','pnl','current_value','net_quantity','total_pnl','available'}
    known=[r for r in items if r.get(sort) is not None];missing=[r for r in items if r.get(sort) is None]
    known.sort(key=lambda r:svc.number(r[sort]) if sort in numeric else str(r[sort]).casefold(),reverse=direction=='desc');items=known+missing
    total=len(items)
    return output(dict(items=items[(page-1)*page_size:page*page_size],total=total,page=page,pages=max(1,(total+page_size-1)//page_size),coverage=coverage,source='BROKER_REPORTED',scope='Current broker book, not an all-time trade ledger' if kind in ('orders','trades') else 'Latest complete per-endpoint snapshot'))
