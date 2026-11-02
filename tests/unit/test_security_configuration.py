from datetime import datetime,timezone
import httpx,pytest
from app.core.config import Settings,settings
from app.security.encryption import encrypt,decrypt
from app.brokers.upstox.adapter import UpstoxAdapter

def test_config_rejects_live_execution_and_bad_keys():
    with pytest.raises(ValueError):Settings(live_trading_enabled=True)
    with pytest.raises(ValueError):Settings(field_encryption_key='not-a-fernet-key')
    with pytest.raises(ValueError):Settings(app_env='production',app_debug=True)

def test_field_encryption_is_randomized_and_authenticated():
    a=encrypt('private-data');b=encrypt('private-data')
    assert a!=b and 'private-data' not in a
    assert decrypt(a)=='private-data'
    with pytest.raises(Exception):decrypt(a[:-4]+'xxxx')

def test_upstox_token_and_profile_contract():
    def handle(request):
        if request.method=='POST':
            assert request.url.host=='api.upstox.com'
            assert b'grant_type=authorization_code' in request.content
            return httpx.Response(200,json={'access_token':'provider-access'})
        assert request.headers['Authorization']=='Bearer provider-access'
        return httpx.Response(200,json={'data':{'user_id':'account-123','is_active':True}})
    adapter=UpstoxAdapter('client','client-secret','https://api.gnkalgo.com/api/v1/brokers/upstox/callback',transport=httpx.MockTransport(handle))
    result=adapter.exchange('one-time-code')
    assert result.account_identifier=='account-123'
    assert result.expires_at>datetime.now(timezone.utc)
    assert 'client-secret' not in adapter.authorization_url('safe-state')

def test_provider_error_is_sanitized():
    adapter=UpstoxAdapter('id','secret','https://api.gnkalgo.com/callback',transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'secret':'do-not-expose'})))
    with pytest.raises(ValueError) as error:adapter.exchange('secret-auth-code')
    assert 'do-not-expose' not in str(error.value)
    assert 'secret-auth-code' not in str(error.value)
