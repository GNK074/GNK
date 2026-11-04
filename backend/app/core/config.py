from decimal import Decimal
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
    disclosure_version: str = Field(default='2026-11-02.1', min_length=1, max_length=60, pattern='^[a-zA-Z0-9._-]+$')
    disclosure_max_age_hours: int = Field(default=24, ge=1, le=168)
    contact_channels_verified: bool = False
    company_registration_verified: bool = False
    company_legal_name: str = ''
    company_sebi_registration: str = ''
    company_basl_membership: str = ''
    company_basl_applicable: bool = False
    company_office_address: str = ''
    company_office_address_verified: bool = False
    enable_mfa: bool = False
    secure_cookies: bool = False
    https_only: bool = False
    individual_broker_setup_enabled: bool = True
    broker_egress_ip: str = ''
    trading_enabled: bool = False
    paper_trading_enabled: bool = True
    live_trading_enabled: bool = False
    upstox_execution_enabled: bool = False
    dhan_execution_enabled: bool = False
    dhan_execution_reference: str = ""
    dhan_tick_size_multiplier: Decimal = Field(default=0,ge=0,le=1)
    dhan_stream_enabled: bool = True
    dhan_oauth_enabled: bool = False
    live_execution_reference: str = ''
    upstox_algo_name: str = ''
    live_price_deviation_percent: int = Field(default=2,ge=1,le=5)
    live_tick_size_multiplier: Decimal = Field(default=0,ge=0,le=1)
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
        if self.company_registration_verified:
            import re
            if not self.company_legal_name.strip() or not re.fullmatch(r'INH[0-9]{9}', self.company_sebi_registration):
                raise ValueError('Verified company publication requires legal entity name and valid SEBI RA registration number')
            if self.company_basl_applicable and not self.company_basl_membership.strip():
                raise ValueError('BASL publication requires verified membership details')
        if self.company_office_address_verified and len(self.company_office_address.strip()) < 20:
            raise ValueError('Provide the full verified office address before enabling map publication')
        if self.live_trading_enabled:
            import ipaddress
            if not self.trading_enabled or not (self.upstox_execution_enabled or self.dhan_execution_enabled) or (self.upstox_execution_enabled and (not self.live_execution_reference.strip() or self.live_execution_reference.strip().lower() in ('false','true','pending') or not self.live_tick_size_multiplier)):
                raise ValueError('Live execution requires explicit Upstox enablement, reviewed reference and verified tick-size multiplier')
            if not ipaddress.ip_address(self.broker_egress_ip).is_global:
                raise ValueError('Live execution requires the registered public egress IP')
        if self.dhan_execution_enabled and (not self.dhan_execution_reference.strip() or self.dhan_execution_reference.strip().lower() in ('false','true','pending') or not self.dhan_tick_size_multiplier or not self.dhan_stream_enabled):
            raise ValueError('Dhan execution requires reviewed reference, verified tick multiplier and private stream service')
        if '\n' in self.upstox_algo_name or '\r' in self.upstox_algo_name:
            raise ValueError('Invalid configured algo name')
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
    try:
        return Path(path).read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        raise RuntimeError('Required mounted secret is missing or unreadable. Check host file permissions with deploy/check_secret_permissions.sh; do not regenerate existing passwords.') from None
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
