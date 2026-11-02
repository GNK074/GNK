"""Validate without printing Pydantic errors, URLs with passwords, or settings."""
import argparse, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--file')
    p.add_argument('--connectivity', action='store_true')
    args = p.parse_args()
    if args.file:
        from dotenv import load_dotenv
        if not Path(args.file).is_file():
            raise SystemExit('Environment file not found.')
        load_dotenv(args.file, override=False)
    try:
        from app.core.config import settings
        if args.connectivity:
            from app.models import identity, trading
            from app.compliance import models as compliance_models
            from app.database.readiness import check_schema
            from app.database.session import engine
            from app.security.authentication import cache
            from sqlalchemy import text
            with engine.connect() as c:
                c.execute(text('SELECT 1'))
                check_schema(c)
            cache.ping()
    except Exception:
        print('Environment/connectivity validation FAILED. Review required variables, secret files, database, pending migrations and Redis. Values are suppressed.', file=sys.stderr)
        return 1
    print('Environment validation passed' + (' including database schema and Redis' if args.connectivity else '') + '. Live execution remains disabled.')
    return 0
if __name__ == '__main__':
    sys.exit(main())
