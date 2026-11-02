"""Individual account validation only. No order APIs are invoked."""
from dataclasses import dataclass,field
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import httpx

@dataclass
class VerifiedSession:
    account_identifier:str
    credentials:dict=field(repr=False)
    expires_at:datetime | None=None
    expiry_basis:str='local_session_deadline'

class ValidationError(ValueError):pass

def session_deadline(hour,minute=0):
    current=datetime.now(ZoneInfo('Asia/Kolkata'))
    deadline=current.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if deadline<=current:deadline+=timedelta(days=1)
    return deadline.astimezone(timezone.utc)

def identity(value):
    if not isinstance(value,(str,int)) or isinstance(value,bool) or not str(value).strip():raise ValidationError('Broker did not return an account identity')
    return str(value).strip()

class ProfileVerifier:
    def __init__(self,transport=None):self.transport=transport
    def request(self,method,url,**kwargs):
        try:
            with httpx.Client(transport=self.transport,timeout=15,follow_redirects=False) as client:
                response=client.request(method,url,**kwargs)
                response.raise_for_status()
                data=response.json()
                if not isinstance(data,dict):raise ValueError()
                return data
        except Exception:
            raise ValidationError('Broker authentication failed. Check your individual API credentials and token validity.') from None

class DhanVerifier(ProfileVerifier):
    def validate(self,c):
        d=self.request('GET','https://api.dhan.co/v2/profile',headers={'access-token':c['access_token']})
        account=identity(d.get('dhanClientId'))
        try:
            raw=d['tokenValidity']
            try:expiry=datetime.strptime(raw,'%d/%m/%Y %H:%M').replace(tzinfo=ZoneInfo('Asia/Kolkata'))
            except ValueError:expiry=datetime.fromisoformat(raw)
            if expiry.tzinfo is None:expiry=expiry.replace(tzinfo=ZoneInfo('Asia/Kolkata'))
            expiry=expiry.astimezone(timezone.utc)
            if expiry<=datetime.now(timezone.utc):raise ValueError()
        except Exception:raise ValidationError('Dhan did not return a usable future token expiry') from None
        return VerifiedSession(account,{'access_token':c['access_token']},expiry,'broker_reported')

class ZerodhaVerifier(ProfileVerifier):
    def validate(self,c):
        response=self.request('GET','https://api.kite.trade/user/profile',headers={'X-Kite-Version':'3','Authorization':'token '+c['api_key']+':'+c['access_token']})
        if response.get('status')!='success':raise ValidationError('Zerodha rejected this API session')
        account=identity(response.get('data',{}).get('user_id'))
        return VerifiedSession(account,{'api_key':c['api_key'],'access_token':c['access_token']},session_deadline(6),'documented_daily_boundary')

class UpstoxVerifier(ProfileVerifier):
    def validate(self,c):
        response=self.request('GET','https://api.upstox.com/v2/user/profile',headers={'Authorization':'Bearer '+c['access_token']})
        d=response.get('data',{})
        if response.get('status')!='success' or d.get('is_active') is not True:raise ValidationError('Upstox account is not active or token is invalid')
        return VerifiedSession(identity(d.get('user_id')),{'access_token':c['access_token']},session_deadline(3,30),'documented_daily_boundary')

class FyersVerifier(ProfileVerifier):
    def validate(self,c):
        response=self.request('GET','https://api-t1.fyers.in/api/v3/profile',headers={'Authorization':c['app_id']+':'+c['access_token']})
        if response.get('s')!='ok' or response.get('code')!=200:raise ValidationError('FYERS rejected this API session')
        return VerifiedSession(identity(response.get('data',{}).get('fy_id')),{'app_id':c['app_id'],'access_token':c['access_token']},session_deadline(6,30),'documented_daily_boundary')

class AngelOneVerifier(ProfileVerifier):
    def validate(self,c):
        from app.core.config import settings
        import ipaddress,socket,uuid
        if not settings.broker_egress_ip:raise ValidationError('The server operator must configure BROKER_EGRESS_IP before Angel One validation')
        try:public_ip=str(ipaddress.ip_address(settings.broker_egress_ip))
        except ValueError:raise ValidationError('Server broker egress IP configuration is invalid') from None
        local_ip=socket.gethostbyname(socket.gethostname())
        mac=':'.join(f'{uuid.getnode():012x}'[i:i+2] for i in range(0,12,2))
        headers={'Authorization':'Bearer '+c['jwt_token'],'X-PrivateKey':c['api_key'],'X-UserType':'USER','X-SourceID':'WEB','X-ClientLocalIP':local_ip,'X-ClientPublicIP':public_ip,'X-MACAddress':mac,'Content-Type':'application/json','Accept':'application/json'}
        response=self.request('GET','https://apiconnect.angelone.in/rest/secure/angelbroking/user/v1/getProfile',headers=headers)
        if response.get('status') is not True:raise ValidationError('Angel One rejected this API session')
        return VerifiedSession(identity(response.get('data',{}).get('clientcode')),{'api_key':c['api_key'],'jwt_token':c['jwt_token']},session_deadline(0),'documented_daily_boundary')

class FivePaisaVerifier(ProfileVerifier):
    def validate(self,c):
        response=self.request('POST','https://Openapi.5paisa.com/VendorsAPI/Service1.svc/GetAccessToken',json={'head':{'Key':c['app_key']},'body':{'RequestToken':c['request_token'],'EncryKey':c['encryption_key'],'UserId':c['user_id']}})
        body=response.get('body',{});status=body.get('Status')
        if type(status) is not int or status!=0 or response.get('head',{}).get('Status')!=0 or not isinstance(body.get('AccessToken'),str) or not body['AccessToken']:raise ValidationError('5paisa request-token exchange was rejected')
        return VerifiedSession(identity(body.get('ClientCode')),{'app_key':c['app_key'],'access_token':body['AccessToken']},session_deadline(23,59),'documented_daily_boundary')

class IciciVerifier(ProfileVerifier):
    def validate(self,c):
        response=self.request('GET','https://api.icicidirect.com/breezeapi/api/v1/customerdetails',json={'SessionToken':c['api_session'],'AppKey':c['app_key']})
        data=response.get('Success',{})
        if response.get('Status')!=200 or response.get('Error') or not isinstance(data,dict) or not data.get('session_token'):raise ValidationError('ICICI Breeze rejected this API session')
        # Provider lifetime is not assumed. A short local deadline requires revalidation.
        return VerifiedSession(identity(data.get('idirect_userid')),{'app_key':c['app_key'],'session_token':data['session_token']},datetime.now(timezone.utc)+timedelta(hours=1),'local_one_hour_deadline')

VERIFIERS={'dhan':DhanVerifier,'zerodha':ZerodhaVerifier,'upstox':UpstoxVerifier,'fyers':FyersVerifier,'angelone':AngelOneVerifier,'5paisa':FivePaisaVerifier,'icici':IciciVerifier}
