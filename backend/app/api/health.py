from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import db
from app.database.readiness import check_schema, SchemaNotReady
from app.security.authentication import cache
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/health')
def health(s: Session=Depends(db)):
    try:
        check_schema(s.connection())
    except SchemaNotReady:
        raise HTTPException(503, "Database migrations are required. Run ./deploy/migrate_database.sh before starting this release.") from None
    s.execute(select(1))
    cache.ping()
    return {'status': 'ok', 'live_trading': False}
