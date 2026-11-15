"""Read-only Dhan pilot, scoped to one authenticated GNK login session."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock, Timer
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.orm import Session

from app.api.users import session_id
from app.brokers.individual.routes import availability
from app.brokers.individual.verifiers import DhanVerifier, ValidationError
from app.core.config import expired, now, settings
from app.database.session import db
from app.portfolio.adapters import PortfolioError, normalize
from app.security.authentication import auth, limit

from .client import DhanClient, DhanError

def prevent_caching(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/dhan/pilot", tags=["Dhan read-only pilot"],
    dependencies=[Depends(prevent_caching)],
)
MAX_SESSIONS = 64
SESSION_TTL = timedelta(minutes=15)


@dataclass(eq=False)
class PilotSession:
    expires_at: datetime
    client: DhanClient | None = field(default=None, repr=False)
    timer: Timer | None = field(default=None, repr=False)
    busy: Lock = field(default_factory=Lock, repr=False)


sessions: dict[tuple[str, str], PilotSession] = {}
session_lock = Lock()


def remove(key, expected=None):
    with session_lock:
        current = sessions.get(key)
        if current is None or (expected is not None and current is not expected):
            return
        del sessions[key]
        if current.timer:
            current.timer.cancel()


def revoke(user_id: str, login_id: str | None = None):
    with session_lock:
        matches = [(key, session) for key, session in sessions.items()
                   if key[0] == user_id and (login_id is None or key[1] == login_id)]
        for key, session in matches:
            del sessions[key]
            if session.timer:
                session.timer.cancel()


def active(key):
    with session_lock:
        session = sessions.get(key)
        if session and session.client and not expired(session.expires_at):
            return session
    return None


def require_available(s):
    allowed, reason = availability(s, "dhan")
    if not allowed:
        raise HTTPException(409, reason)


class ConnectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    access_token: SecretStr = Field(min_length=1, max_length=16384)
    owns_account: Literal[True]


@router.get("/session")
def status(request: Request, u=Depends(auth), s: Session=Depends(db)):
    require_available(s)
    session = active((u.id, session_id(request)))
    return {"connected": session is not None, "expires_at": session.expires_at if session else None}


@router.post("/session")
def connect(data: ConnectInput, request: Request, u=Depends(auth), s: Session=Depends(db)):
    require_available(s)
    limit(request, "dhan-pilot-connect", u.id)
    key = (u.id, session_id(request))
    token = data.access_token.get_secret_value()
    if any(character.isspace() for character in token):
        raise HTTPException(422, "Enter a Dhan access token without whitespace.")

    with session_lock:
        previous = sessions.get(key)
        if previous and previous.client is None:
            raise HTTPException(409, "Dhan verification is already running.")
        if previous is None and len(sessions) >= MAX_SESSIONS:
            raise HTTPException(503, "Dhan pilot session capacity reached.")
        if previous and previous.timer:
            previous.timer.cancel()
        pending = PilotSession(now() + SESSION_TTL)
        sessions[key] = pending
    try:
        verified = DhanVerifier().validate({"client_id": data.client_id, "access_token": token})
        if verified.account_identifier != data.client_id or not verified.expires_at or expired(verified.expires_at):
            raise HTTPException(422, "The broker did not verify this Dhan account and token.")
        client = DhanClient(data.client_id, token)
        with session_lock:
            if sessions.get(key) is not pending:
                raise HTTPException(409, "Dhan verification was cancelled.")
            pending.expires_at = min(pending.expires_at, verified.expires_at)
            pending.client = client
            pending.timer = Timer(max(0, (pending.expires_at - now()).total_seconds()), remove, args=(key, pending))
            pending.timer.daemon = True
            pending.timer.start()
        return {"connected": True, "expires_at": pending.expires_at}
    except (ValidationError, DhanError):
        remove(key, pending)
        raise HTTPException(422, "Dhan verification failed. Check your client ID and token.") from None
    except Exception:
        remove(key, pending)
        raise


@router.delete("/session")
def disconnect(request: Request, u=Depends(auth)):
    remove((u.id, session_id(request)))
    return {"connected": False}


@router.get("/portfolio/{kind}")
def portfolio(kind: Literal["holdings", "positions", "funds", "orders", "trades"], request: Request, u=Depends(auth), s: Session=Depends(db)):
    require_available(s)
    limit(request, "dhan-pilot-portfolio", u.id)
    return read(request, u.id, lambda client: normalize("dhan", kind, client.read(kind)))


@router.get("/ip")
def ip_status(request: Request, u=Depends(auth), s: Session=Depends(db)):
    require_available(s)
    limit(request, "dhan-pilot-ip", u.id)
    if not settings.broker_egress_ip:
        return {"data": {"state": "GNK_EGRESS_IP_NOT_CONFIGURED"}}

    def check(client):
        if client.ip_whitelist_matches(settings.broker_egress_ip):
            return {"state": "MATCH"}
        return {"state": "NO_MATCH"}

    return read(request, u.id, check)


def read(request, user_id, operation):
    key = (user_id, session_id(request))
    session = active(key)
    if session is None:
        raise HTTPException(409, "Reconnect to Dhan to continue.")
    if not session.busy.acquire(blocking=False):
        raise HTTPException(429, "Another Dhan request is running.")
    try:
        data = operation(session.client)
        if active(key) is not session:
            raise HTTPException(409, "The Dhan session changed. Reconnect or refresh.")
        return {"data": data, "fetched_at": now()}
    except DhanError as error:
        if error.code == "SESSION_EXPIRED":
            remove(key, session)
            raise HTTPException(409, "The Dhan session expired. Reconnect to continue.") from None
        raise HTTPException(502, "Dhan could not complete the read.") from None
    except PortfolioError:
        raise HTTPException(502, "Dhan returned an unsupported portfolio response.") from None
    finally:
        session.busy.release()
