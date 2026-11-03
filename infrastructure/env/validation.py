"""Validate deployment stages without printing settings, input values or credentials."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))

# Only messages authored by this application may be exposed. Never print a
# Pydantic error's input, arbitrary message, context, exception repr or URL.
SAFE_MESSAGES={
    'Live execution requires explicit Upstox enablement, reviewed reference and verified tick-size multiplier':
        'Live activation requires TRADING_ENABLED, UPSTOX_EXECUTION_ENABLED, LIVE_EXECUTION_REFERENCE and a positive verified LIVE_TICK_SIZE_MULTIPLIER. Check spelling of LIVE_EXECUTION_REFERENCE.',
    'Live execution requires the registered public egress IP':
        'BROKER_EGRESS_IP must be the registered public egress IP.',
    'Distribution approval requires a verified written reference':
        'MARKETDATA_DISTRIBUTION_APPROVED=true requires an actual MARKETDATA_APPROVAL_REFERENCE; blank, true, false and pending are invalid references.',
    'Production secrets must be configured':'Required production secrets are missing or contain placeholders. Preserve existing encryption/database secrets.',
    'Production requires independent SECRET_KEY':'SECRET_KEY must be independent of the JWT key and at least 32 characters.',
    'JWT secret requires 32+ characters':'JWT_SECRET_KEY or JWT_SECRET must have at least 32 characters.',
    'Invalid field encryption key':'FIELD_ENCRYPTION_KEY or a previous key is invalid. Preserve the existing keys.',
    'Production requires debug off, HTTPS, secure cookies and MFA':'Production requires APP_DEBUG=false, HTTPS_ONLY=true, SECURE_COOKIES=true and ENABLE_MFA=true.',
    'Production requires HTTPS origins without credentials':'Production frontend/backend/CORS origins must use HTTPS without embedded credentials.',
    'Production requires postgresql+psycopg':'Production DATABASE_URL must use postgresql+psycopg.',
    'Production connectivity checks cannot be disabled':'Production requires STARTUP_CONNECTIVITY_CHECK=true.',
    'Production requires real SMTP with TLS':'Production requires a real SMTP host and SMTP_USE_TLS=true.',
    'Production requires authenticated Redis':'Configure authenticated Redis using the existing password or mounted secret.',
    'Unsupported configured feed mode':'MARKETDATA_ALLOWED_MODES contains an unsupported feed mode.',
    'Unsupported configured exchange segment':'MARKETDATA_ALLOWED_SEGMENTS contains an unsupported exchange segment.',
}

def configuration_failure(stage,error):
    from pydantic import ValidationError
    print(f'FAIL {stage} configuration.',file=sys.stderr)
    if isinstance(error,ValidationError):
        for item in error.errors(include_input=False,include_context=False,include_url=False):
            # Settings models use fixed field names; suppress dynamic location text.
            field=next((x for x in item.get('loc',()) if isinstance(x,str) and x.replace('_','').isalnum()),'model')
            message=item.get('msg','').removeprefix('Value error, ')
            hint=SAFE_MESSAGES.get(message)
            print('  '+(hint or f'Check {field.upper()}; a required value, type or format is invalid.'),file=sys.stderr)
    else:print('  Required configuration or a mounted secret could not be loaded. Values are suppressed.',file=sys.stderr)
    return 1

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--file');parser.add_argument('--connectivity',action='store_true');args=parser.parse_args()
    if args.file:
        from dotenv import load_dotenv
        if not Path(args.file).is_file():raise SystemExit('Environment file not found.')
        load_dotenv(args.file,override=False)
    try:from app.core.config import settings
    except Exception as error:return configuration_failure('application',error)
    print('PASS application configuration.')
    try:from app.market_data.config import market_settings
    except Exception as error:return configuration_failure('market-data',error)
    print('PASS market-data configuration.')
    if args.connectivity:
        try:
            from app.models import identity,trading
            from app.compliance import models as compliance_models
            from app.execution import models as execution_models
            from app.market_data import models as market_models
            from app.database.session import engine
            from sqlalchemy import text
            with engine.connect() as connection:connection.execute(text('SELECT 1'))
        except Exception:
            print('FAIL database connection or mounted secret. Verify the existing runtime credentials, grants and PostgreSQL service. Values are suppressed.',file=sys.stderr);return 1
        print('PASS database connection.')
        try:
            from app.database.readiness import check_schema
            with engine.connect() as connection:check_schema(connection)
        except Exception:
            print('FAIL database schema. Run ./deploy/migrate_database.sh with the matching release before starting services. Values are suppressed.',file=sys.stderr);return 1
        print('PASS database schema.')
        try:
            from app.security.authentication import cache
            cache.ping()
        except Exception:
            print('FAIL Redis connection or authentication. Verify the Redis service and existing mounted secret. Values are suppressed.',file=sys.stderr);return 1
        print('PASS Redis connection.')
    print('Environment validation passed'+(' including database schema and Redis' if args.connectivity else '')+('. Live placement configured; broker/account/strategy and risk gates still apply.' if settings.live_trading_enabled else '. Live execution remains disabled.'))
    return 0
if __name__=='__main__':sys.exit(main())
