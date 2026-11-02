from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import httpx,pytest
from app.brokers.individual.verifiers import VERIFIERS,ValidationError
from app.core.config import settings

CASES={
'dhan':({'client_id':'ACCT123','access_token':'private-token'},{'dhanClientId':'ACCT123','tokenValidity':(datetime.now(ZoneInfo('Asia/Kolkata'))+timedelta(hours=2)).strftime('%d/%m/%Y %H:%M')},'api.dhan.co','/v2/profile','GET'),
'zerodha':({'client_id':'ACCT123','api_key':'own-app-key','access_token':'private-token'},{'status':'success','data':{'user_id':'ACCT123'}},'api.kite.trade','/user/profile','GET'),
'upstox':({'client_id':'ACCT123','access_token':'private-token'},{'status':'success','data':{'user_id':'ACCT123','is_active':True}},'api.upstox.com','/v2/user/profile','GET'),
'fyers':({'client_id':'ACCT123','app_id':'own-app-100','access_token':'private-token'},{'s':'ok','code':200,'data':{'fy_id':'ACCT123'}},'api-t1.fyers.in','/api/v3/profile','GET'),
'angelone':({'client_id':'ACCT123','api_key':'own-app-key','jwt_token':'private-token'},{'status':True,'data':{'clientcode':'ACCT123'}},'apiconnect.angelone.in','/rest/secure/angelbroking/user/v1/getProfile','GET'),
'5paisa':({'client_id':'ACCT123','app_key':'own-app','encryption_key':'own-encryption-key','user_id':'api-user','request_token':'private-request'},{'head':{'Status':0},'body':{'Status':0,'ClientCode':'ACCT123','AccessToken':'exchanged-token'}},'openapi.5paisa.com','/VendorsAPI/Service1.svc/GetAccessToken','POST'),
'icici':({'client_id':'ACCT123','app_key':'own-app','api_session':'private-session'},{'Status':200,'Error':None,'Success':{'idirect_userid':'ACCT123','session_token':'exchanged-session'}},'api.icicidirect.com','/breezeapi/api/v1/customerdetails','GET')}

@pytest.mark.parametrize('broker',list(CASES))
def test_individual_identity_contracts_do_not_place_orders(broker,monkeypatch):
    credentials,response,host,path,method=CASES[broker]
    monkeypatch.setattr(settings,'broker_egress_ip','8.8.8.8')
    requests=[]
    def handle(request):
        requests.append(request)
        assert request.url.host.lower()==host and request.url.path==path and request.method==method
        assert '/order' not in request.url.path.lower()
        if broker=='dhan':assert request.headers['access-token']=='private-token'
        if broker=='zerodha':assert request.headers['Authorization']=='token own-app-key:private-token'
        if broker=='fyers':assert request.headers['Authorization']=='own-app-100:private-token'
        if broker=='5paisa':assert b'"RequestToken":"private-request"' in request.content
        return httpx.Response(200,json=response)
    result=VERIFIERS[broker](transport=httpx.MockTransport(handle)).validate(credentials)
    assert result.account_identifier=='ACCT123' and result.expires_at is not None
    assert result.expires_at>datetime.now(result.expires_at.tzinfo)
    assert len(requests)==1
    assert 'private-token' not in repr(result)

@pytest.mark.parametrize('broker',list(CASES))
def test_bad_credentials_are_sanitized(broker,monkeypatch):
    monkeypatch.setattr(settings,'broker_egress_ip','8.8.8.8')
    verifier=VERIFIERS[broker](transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'error':'private-provider-secret'})))
    with pytest.raises(ValidationError) as failure:verifier.validate(CASES[broker][0])
    assert 'private-provider-secret' not in str(failure.value)
    assert 'private-token' not in str(failure.value)

def test_angel_one_requires_operator_egress_configuration(monkeypatch):
    monkeypatch.setattr(settings,'broker_egress_ip','')
    with pytest.raises(ValidationError,match='BROKER_EGRESS_IP'):VERIFIERS['angelone']().validate(CASES['angelone'][0])

def test_dhan_expired_token_is_rejected():
    verifier=VERIFIERS['dhan'](transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'dhanClientId':'ACCT123','tokenValidity':'01/01/2020 00:00'})))
    with pytest.raises(ValidationError):verifier.validate(CASES['dhan'][0])
