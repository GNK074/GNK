from sqlalchemy import select
from app.core.config import settings,read_secret,now
from app.security.encryption import encrypt,decrypt
from app.market_data.config import market_settings as cfg
from app.market_data.models import MarketProviderSecret
from app.market_data.providers.base import ProviderError

def synchronize_secret(s):
    token=read_secret(cfg.upstox_analytics_token_file) if cfg.upstox_analytics_token_file else cfg.upstox_analytics_token.get_secret_value()
    if not token:return
    row=s.get(MarketProviderSecret,'upstox')
    if row:
        try:
            if decrypt(row.ciphertext)==token:return
        except Exception:pass
        row.ciphertext=encrypt(token);row.key_version=settings.encryption_key_version;row.updated=now()
    else:s.add(MarketProviderSecret(provider='upstox',ciphertext=encrypt(token),key_version=settings.encryption_key_version))
    s.commit()

def provider_token(s):
    row=s.get(MarketProviderSecret,'upstox')
    if not row:raise ProviderError('PROVIDER_CREDENTIAL_MISSING')
    try:return decrypt(row.ciphertext)
    except Exception:raise ProviderError('PROVIDER_KEY_UNREADABLE') from None
