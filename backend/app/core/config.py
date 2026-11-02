import hashlib
import os
import uuid
from datetime import datetime, timezone
UTC = timezone.utc

def now():
    return datetime.now(UTC)

def ident():
    return str(uuid.uuid4())

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()
PROD = os.getenv('ENVIRONMENT') == 'production'
SECRET = os.getenv('JWT_SECRET', '')
ORIGIN = os.getenv('FRONTEND_URL', 'http://localhost:8080')

def expired(dt):
    return dt.replace(tzinfo=UTC) <= now()
if len(SECRET) < 32:
    raise RuntimeError('JWT_SECRET must contain at least 32 characters')
