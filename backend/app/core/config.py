import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore', hide_input_in_errors=True, populate_by_name=True)
    app_env: Literal['development', 'testing', 'production'] = Field(default='development', validation_alias=AliasChoices('APP_ENV', 'ENVIRONMENT'))
    app_debug: bool = False
    app_version: str = '0.3.0'
    frontend_url: str = 'http://localhost:8080'
    backend_url: str = 'http://localhost:8080'
    cors_allowed_origins: str = ''
    database_url: SecretStr = SecretStr('sqlite:///./gnk.db')
    database_password_file: str = ''
    db_pool_size: int = Field(default=20, ge=1, le=200)
    db_max_overflow: int = Field(default=30, ge=0, le=200)
    db_pool_timeout: int = Field(default=30, ge=1)
    db_pool_recycle: int = Field(default=1800, ge=60)
    redis_url: SecretStr = SecretStr('redis://redis:6379/0')
    redis_password: SecretStr = SecretStr('')
    redis_password_file: str = ''
    redis_max_connections: int = Field(default=100, ge=1)
    secret_key: SecretStr = SecretStr('')
    jwt_secret_key: SecretStr = Field(validation_alias=AliasChoices('JWT_SECRET_KEY', 'JWT_SECRET'))
    jwt_algorithm: Literal['HS256'] = 'HS256'
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    field_encryption_key: SecretStr
    field_encryption_previous_keys: SecretStr = SecretStr('')
    encryption_key_version: str = 'v1'
    enable_mfa: bool = False
    secure_cookies: bool = False
    https_only: bool = False
    trading_enabled: bool = False
    paper_trading_enabled: bool = True
    live_trading_enabled: bool = False
    smtp_host: str = 'mailpit'
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str = ''
    smtp_password: SecretStr = SecretStr('')
    smtp_from_email: str = 'noreply@gnkalgo.local'
    smtp_use_tls: bool = False
    broker_callback_state_ttl_seconds: int = Field(default=600, ge=60, le=900)
    startup_connectivity_check: bool = True

    @model_validator(mode='after')
    def validate_configuration(self):
        if len(self.jwt_secret_key.get_secret_value()) < 32:
            raise ValueError('JWT secret requires 32+ characters')
        try:
            for k in [self.field_encryption_key.get_secret_value()] + [x for x in self.field_encryption_previous_keys.get_secret_value().split(',') if x]:
                Fernet(k.encode())
        except Exception:
            raise ValueError('Invalid field encryption key') from None
        if self.live_trading_enabled:
            raise ValueError('Live execution is unavailable in this release; keep LIVE_TRADING_ENABLED=false')
        if self.app_env == 'production':
            values = [self.jwt_secret_key.get_secret_value(), self.secret_key.get_secret_value(), self.smtp_password.get_secret_value()]
            if any((not v or any((marker in v.upper() for marker in ['REPLACE-WITH', 'CHANGE_ME', 'CONFIGURE_', 'GENERATE_'])) for v in values)):
                raise ValueError('Production secrets must be configured')
            if self.app_debug or not self.secure_cookies or (not self.https_only) or (not self.enable_mfa):
                raise ValueError('Production requires debug off, HTTPS, secure cookies and MFA')
            if any((urlsplit(x).scheme != 'https' or not urlsplit(x).hostname or urlsplit(x).username for x in [self.frontend_url, self.backend_url] + self.origins)):
                raise ValueError('Production requires HTTPS origins without credentials')
            if not self.database_url.get_secret_value().startswith('postgresql+psycopg://'):
                raise ValueError('Production requires postgresql+psycopg')
            if not self.startup_connectivity_check:
                raise ValueError('Production connectivity checks cannot be disabled')
            if len(self.secret_key.get_secret_value()) < 32 or self.secret_key == self.jwt_secret_key:
                raise ValueError('Production requires independent SECRET_KEY')
            if not self.smtp_use_tls or self.smtp_host == 'mailpit':
                raise ValueError('Production requires real SMTP with TLS')
            if not (self.redis_password.get_secret_value() or self.redis_password_file or urlsplit(self.redis_url.get_secret_value()).password):
                raise ValueError('Production requires authenticated Redis')
        return self

    @property
    def origins(self):
        return [x.strip() for x in self.cors_allowed_origins.split(',') if x.strip()] or [self.frontend_url]

def read_secret(path):
    return Path(path).read_text(encoding='utf-8').strip()
settings = Settings()
UTC = timezone.utc
PROD = settings.app_env == 'production'
SECRET = settings.jwt_secret_key.get_secret_value()
ORIGIN = settings.frontend_url

def now():
    return datetime.now(UTC)

def ident():
    return str(uuid.uuid4())

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def expired(dt):
    return (dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)) <= now()
