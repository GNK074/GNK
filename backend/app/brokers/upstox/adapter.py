from app.brokers.base.broker_interface import BrokerTokens
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import httpx

class UpstoxAdapter:
    """OAuth and read-only identity validation; no live order implementation."""
    docs = 'https://upstox.com/developer/api-documentation/authentication/'

    def __init__(self, client_id, client_secret, redirect_uri, transport=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.transport = transport

    def authorization_url(self, state):
        return 'https://api.upstox.com/v2/login/authorization/dialog?' + urlencode(dict(response_type='code', client_id=self.client_id, redirect_uri=self.redirect_uri, state=state))

    def exchange(self, code):
        try:
            with httpx.Client(timeout=15, transport=self.transport, follow_redirects=False) as client:
                response = client.post('https://api.upstox.com/v2/login/authorization/token', data=dict(code=code, client_id=self.client_id, client_secret=self.client_secret, redirect_uri=self.redirect_uri, grant_type='authorization_code'))
                response.raise_for_status()
                token = response.json()['access_token']
                profile = client.get('https://api.upstox.com/v2/user/profile', headers={'Authorization': 'Bearer ' + token})
                profile.raise_for_status()
                data = profile.json()['data']
                if not data.get('user_id') or not data.get('is_active'):
                    raise ValueError()
                local = datetime.now(ZoneInfo('Asia/Kolkata'))
                expiry = local.replace(hour=3, minute=30, second=0, microsecond=0)
                if expiry <= local:
                    expiry += timedelta(days=1)
                return BrokerTokens(token, str(data['user_id']), expires_at=expiry.astimezone(timezone.utc))
        except Exception:
            raise ValueError('Broker authorization or account validation failed') from None
