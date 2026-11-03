"""Regression: schema maintenance must work with an incomplete live rollout."""
from pathlib import Path
import pytest,yaml
from app.core.config import Settings
from app.market_data.config import MarketSettings

def test_migrator_overrides_incomplete_live_configuration(monkeypatch):
    baseline={
        'APP_ENV':'production','ENVIRONMENT':'production',
        'JWT_SECRET_KEY':'migration-test-jwt-key-with-48-characters-1234567890',
        'SECRET_KEY':'independent-migration-session-key-12345678901234567890',
        'FIELD_ENCRYPTION_KEY':'dGVzdC1vbmx5LWZpZWxkLWtleS0wMDAwMDAwMDAwMDA=',
        'FRONTEND_URL':'https://gnkalgo.com','BACKEND_URL':'https://api.gnkalgo.com',
        'SMTP_HOST':'smtp.example.org','SMTP_PASSWORD':'offline-test-value',
        'SMTP_USE_TLS':'true','SECURE_COOKIES':'true','HTTPS_ONLY':'true','ENABLE_MFA':'true',
        'DATABASE_URL':'postgresql+psycopg://gnk@postgres:5432/gnk',
        'REDIS_PASSWORD_FILE':'/run/secrets/redis_password','STARTUP_CONNECTIVITY_CHECK':'true',
        'TRADING_ENABLED':'true','LIVE_TRADING_ENABLED':'true','UPSTOX_EXECUTION_ENABLED':'false',
        'LIVE_EXECUTION_REFERENCE':'','LIVE_TICK_SIZE_MULTIPLIER':'0',
        'MARKETDATA_DISTRIBUTION_APPROVED':'true','MARKETDATA_APPROVAL_REFERENCE':'false',
    }
    for key,value in baseline.items():monkeypatch.setenv(key,value)
    # These inherited runtime settings correctly fail closed.
    with pytest.raises(ValueError,match='Live execution requires'):Settings()
    with pytest.raises(ValueError,match='Distribution approval requires'):MarketSettings()
    root=Path(__file__).resolve().parents[2]
    config=yaml.safe_load((root/'docker-compose.migrate.yml').read_text())
    for key,value in config['services']['migrator']['environment'].items():monkeypatch.setenv(key,str(value))
    settings=Settings();market=MarketSettings()
    assert settings.app_env=='production'
    assert not settings.trading_enabled and not settings.live_trading_enabled and not settings.upstox_execution_enabled
    assert settings.startup_connectivity_check and settings.enable_mfa and settings.secure_cookies
    assert not market.upstox_enabled and not market.marketdata_distribution_approved
