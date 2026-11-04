"""GNK-owned browser consent workflow; no broker PIN/TOTP secrets collected."""
from datetime import timedelta
import secrets,json,re,logging
from urllib.parse import urlencode
import jwt,httpx
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel,SecretStr,ConfigDict,Field
from typing import Literal
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from app.core.config import settings,SECRET,now,digest,expired
from app.database.session import db
from app.database.tenancy import set_context
from app.security.authentication import auth,limit
from app.security.encryption import seal_credentials,open_credentials
from app.models.identity import User,LoginSession
from app.models.trading import BrokerAccount
from app.services.accounts import audit
from .models import ConsentAttempt
from .client import DhanError
router=APIRouter(prefix='/api/v1/dhan/oauth',tags=['Broker consent'])
COOKIE='gnk_dhan_consent'

class _AuthLogFilter(logging.Filter):
    def filter(self,record):
        if any(key in record.getMessage() for key in ('tokenId=','pin=','totp=')):
            record.msg='Broker authentication transport event (sensitive query suppressed)';record.args=();record.exc_info=None
        return True
logging.getLogger('httpx').addFilter(_AuthLogFilter())

class ConsentProvider:
    def __init__(self,transport=None):self.transport=transport
    def request(self,method,path,params,app_id,app_secret):
        try:
            with httpx.Client(transport=self.transport,timeout=12,follow_redirects=False,trust_env=False) as client:
                with client.stream(method,'https://auth.dhan.co/app/'+path,params=params,headers={'app_id':app_id,'app_secret':app_secret}) as response:
                    if response.status_code!=200:raise ValueError()
                    raw=bytearray()
                    for part in response.iter_bytes():
                        raw.extend(part)
                        if len(raw)>65536:raise ValueError()
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError()
            return value
        except Exception:raise DhanError('BROKER_CONSENT_UNAVAILABLE') from None
    def start(self,client_id,app_id,app_secret):
        value=self.request('POST','generate-consent',{'client_id':client_id},app_id,app_secret)
        consent=value.get('consentAppId')
        if value.get('status')!='success' or not isinstance(consent,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',consent):raise DhanError('BROKER_CONSENT_REJECTED')
        return 'https://auth.dhan.co/login/consentApp-login?'+urlencode({'consentAppId':consent})
    def consume(self,token_id,app_id,app_secret):return self.request('GET','consumeApp-consent',{'tokenId':token_id},app_id,app_secret)

class ConsentInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client_id:str=Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    app_id:SecretStr
    app_secret:SecretStr
    owns_account:Literal[True]
    terms_accepted:Literal[True]

@router.post('/start')
def start(data:ConsentInput,request:Request,response:Response,u=Depends(auth),s=Depends(db)):
    if not settings.dhan_oauth_enabled:raise HTTPException(409,'Broker browser login is not enabled by the operator')
    limit(request,'dhan-consent',u.id)
    values={k:getattr(data,k).get_secret_value().strip() for k in ('app_id','app_secret')}
    if any(not 1<=len(v)<=4096 or '\n' in v or '\r' in v for v in values.values()):raise HTTPException(422,'Invalid application credential format')
    from app.brokers.individual.routes import availability
    ready,reason=availability(s,'dhan')
    if not ready:raise HTTPException(409,reason)
    try:url=ConsentProvider().start(data.client_id,**values)
    except DhanError as e:raise HTTPException(409,e.code) from None
    a=s.scalar(select(BrokerAccount).where(BrokerAccount.user_id==u.id,BrokerAccount.broker=='dhan',BrokerAccount.account_identifier==data.client_id))
    try:
        if not a:a=BrokerAccount(user_id=u.id,broker='dhan',account_identifier=data.client_id,status='pending');s.add(a);s.flush()
        claims=jwt.decode(request.cookies.get('access',''),SECRET,algorithms=['HS256'],audience='gnk-web',issuer='gnk-api')
        nonce=secrets.token_urlsafe(32);expires=now()+timedelta(minutes=10)
        s.execute(delete(ConsentAttempt).where(ConsentAttempt.user_id==u.id,ConsentAttempt.expires_at<now()))
        row=ConsentAttempt(user_id=u.id,account_id=a.id,session_id=claims['sid'],state_hash=digest(nonce),secret_ciphertext=seal_credentials(u.id,a.id,values),expires_at=expires)
        s.add(row);audit(s,u.id,'broker_consent_started');s.commit()
        proof=jwt.encode({'sub':u.id,'sid':claims['sid'],'nonce':nonce,'aud':'gnk-broker-consent','iss':'gnk-api','exp':expires},SECRET,algorithm='HS256')
        response.set_cookie(COOKIE,proof,max_age=600,httponly=True,secure=settings.secure_cookies,samesite='lax',path='/api/v1/dhan/oauth')
        return {'authorization_url':url,'expires_in':600,'callback_url':settings.frontend_url.rstrip('/')+'/api/v1/dhan/oauth/callback'}
    except IntegrityError:
        s.rollback();raise HTTPException(409,'This broker identity cannot be connected to this GNK account') from None

@router.get('/callback')
def callback(request:Request,tokenId:str='',s=Depends(db)):
    result='failed';uid=None
    try:
        if not settings.dhan_oauth_enabled or not 1<=len(tokenId)<=4096 or any(c in tokenId for c in '\r\n'):raise ValueError()
        claims=jwt.decode(request.cookies.get(COOKIE,''),SECRET,algorithms=['HS256'],audience='gnk-broker-consent',issuer='gnk-api');uid=claims['sub']
        user=s.get(User,uid);session=s.get(LoginSession,claims['sid'])
        if not user or not user.active or not user.verified or not session or session.user_id!=uid or session.revoked or not session.mfa_complete or expired(session.expires):raise ValueError()
        set_context(s,uid)
        row=s.scalar(select(ConsentAttempt).where(ConsentAttempt.user_id==uid,ConsentAttempt.state_hash==digest(claims['nonce'])).with_for_update())
        if not row or row.session_id!=session.id or row.consumed or expired(row.expires_at):raise ValueError()
        account=s.scalar(select(BrokerAccount).where(BrokerAccount.id==row.account_id,BrokerAccount.user_id==uid))
        if not account or account.broker!='dhan':raise ValueError()
        values=open_credentials(uid,account.id,row.secret_ciphertext)
        row.consumed=True;row.secret_ciphertext='';s.commit()
        raw=ConsentProvider().consume(tokenId,**values)
        if str(raw.get('dhanClientId'))!=account.account_identifier or not isinstance(raw.get('accessToken'),str):raise ValueError()
        from app.brokers.individual.routes import connect_individual,IndividualInput
        connect_individual('dhan',IndividualInput(credentials={'client_id':account.account_identifier,'access_token':raw['accessToken']},owns_account=True,terms_accepted=True),request,user,s)
        result='connected'
    except Exception:
        s.rollback()
        if uid:
            try:audit(s,uid,'broker_consent_failed');s.commit()
            except Exception:s.rollback()
    response=RedirectResponse(settings.frontend_url.rstrip('/')+'/user/dhan?oauth='+result,status_code=303)
    response.delete_cookie(COOKIE,path='/api/v1/dhan/oauth');response.headers['Referrer-Policy']='no-referrer';response.headers['Cache-Control']='no-store'
    return response
