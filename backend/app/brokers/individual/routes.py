from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,SecretStr,field_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.config import settings,now
from app.database.session import db
from app.models.identity import User
from app.models.trading import BrokerAccount,BrokerCredential,BrokerIntegration
from app.security.authentication import auth,limit
from app.security.encryption import seal_credentials
from app.services.accounts import audit
from app.brokers.gateway import account_public
from .catalog import SETUP
from .verifiers import VERIFIERS,ValidationError
router=APIRouter(prefix='/api/v1/brokers')

class IndividualInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    credentials:dict[str,SecretStr]
    owns_account:Literal[True]
    terms_accepted:Literal[True]
    @field_validator('credentials')
    @classmethod
    def bounded(cls,value):
        if not 1<=len(value)<=10:raise ValueError('Invalid credential field count')
        if any(not 1<=len(v.get_secret_value())<=16384 or '\r' in v.get_secret_value() or '\n' in v.get_secret_value() for v in value.values()):raise ValueError('Credential fields must be nonempty, single-line values')
        return value

def availability(s,broker):
    if not settings.individual_broker_setup_enabled:return False,'Individual broker setup is disabled by the server operator'
    if broker not in VERIFIERS:return False,'A broker-specific individual account adapter is not implemented yet'
    config=s.get(BrokerIntegration,broker)
    if config and (config.mode in ('DISABLED','PLATFORM') or not config.auth_verified):return False,'The operator configuration currently blocks individual credentials for this broker'
    if broker=='angelone' and not settings.broker_egress_ip:return False,'The server operator must configure BROKER_EGRESS_IP for Angel One'
    return True,None

def setup_payload(s,broker):
    details=SETUP.get(broker)
    ready,reason=availability(s,broker)
    return {'broker':broker,'setup_available':True,'individual_available':ready,'connection_blocker':reason,'mode':'INDIVIDUAL','fields':details['fields'] if details else [],'steps':details['steps'] if details else ['Broker-specific connection implementation is still required. No credentials will be collected until it exists.'],'docs_url':details['docs'] if details else None,'portal_url':details['portal'] if details else None,'live_trading':False,'connection_method':'individual_credentials' if broker in VERIFIERS else None}

@router.get('/{broker}/setup')
def setup(broker:str,u=Depends(auth),s:Session=Depends(db)):
    from app.brokers.routes import BROKERS
    candidates={b.lower().replace(' ','-') for b in BROKERS}|set(SETUP)
    if broker not in candidates:raise HTTPException(404,'Unknown broker')
    return setup_payload(s,broker)

@router.post('/{broker}/individual',status_code=201)
def connect_individual(broker:str,data:IndividualInput,request:Request,u=Depends(auth),s:Session=Depends(db)):
    limit(request,'individual-broker-connect',u.id)
    ready,reason=availability(s,broker)
    if not ready:raise HTTPException(409,reason)
    expected_fields={f['name'] for f in SETUP[broker]['fields']}
    if set(data.credentials)!=expected_fields:raise HTTPException(422,'Supply exactly the individual credential fields shown for this broker')
    credentials={name:value.get_secret_value().strip() for name,value in data.credentials.items()}
    try:
        verified=VERIFIERS[broker]().validate(credentials)
    except ValidationError as error:
        raise HTTPException(422,str(error)) from None
    except Exception:
        raise HTTPException(502,'Broker validation could not complete; no connection was saved') from None
    if verified.account_identifier!=credentials['client_id']:
        raise HTTPException(422,'The verified broker identity does not match the client ID entered')
    from app.core.config import expired
    if not verified.expires_at or expired(verified.expires_at):raise HTTPException(422,'A current broker session with a future local deadline is required')
    try:
        s.scalar(select(User).where(User.id==u.id).with_for_update())
        account=s.scalar(select(BrokerAccount).where(BrokerAccount.broker==broker,BrokerAccount.account_identifier==verified.account_identifier).with_for_update())
        if account and account.user_id!=u.id:raise HTTPException(409,'This broker account is already linked to a different GNK account')
        if not account:
            account=BrokerAccount(user_id=u.id,broker=broker,account_identifier=verified.account_identifier);s.add(account);s.flush()
        account.status='connected';account.kill_switch=True;account.live_authorized=False
        credential=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==account.id,BrokerCredential.user_id==u.id))
        if not credential:
            credential=BrokerCredential(user_id=u.id,account_id=account.id,ciphertext='',key_version=settings.encryption_key_version);s.add(credential)
        credential.ciphertext=seal_credentials(u.id,account.id,{'credentials':verified.credentials,'connection_method':'individual_credentials','verified_at':now().isoformat(),'expiry_basis':verified.expiry_basis})
        credential.key_version=settings.encryption_key_version;credential.expires_at=verified.expires_at
        from app.portfolio.service import connected
        connected(s,u.id,account.id,broker)
        audit(s,u.id,'individual_broker_identity_verified:'+broker);s.commit()
    except IntegrityError:
        s.rollback();raise HTTPException(409,'This broker account could not be linked because its identity is already registered') from None
    value=account_public(account)
    value.update(expires_at=verified.expires_at,verified_at=now(),expiry_basis=verified.expiry_basis,message='Broker & Exchange settings created successfully!')
    return value
