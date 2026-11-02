from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ConnectionCheck:
    name: str
    status: str
    detail: str

@dataclass(frozen=True)
class BrokerIdentity:
    client_id: str
    expires_at: datetime | None
    segments: tuple[str, ...]

class BrokerAdapter(ABC):
    """Contract only. Implementations require official documentation and approval.

    Never accept broker passwords/PINs/OTPs. Never place orders during validation.
    Credentials must remain server-side and be encrypted before persistence.
    """
    @abstractmethod
    def initiate(self, callback_url: str, state: str) -> str: ...
    @abstractmethod
    def exchange(self, callback: dict, expected_state: str) -> BrokerIdentity: ...
    @abstractmethod
    def validate(self) -> list[ConnectionCheck]: ...
    @abstractmethod
    def disconnect(self) -> None: ...

# Deliberately empty: no broker has completed access/compliance verification.
APPROVED_ADAPTERS: dict[str, type[BrokerAdapter]] = {}
