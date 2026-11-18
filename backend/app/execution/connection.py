"""Venue-neutral boundary for real-money execution."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol


@dataclass(frozen=True)
class LiveOrderIntent:
    client_order_id: str
    instrument_id: str
    side: Literal['BUY', 'SELL']
    quantity: int
    limit_price: Decimal


class ExecutionConnection(Protocol):
    """Accept durable GNK order intents and return external order references."""

    def place(self, intent: LiveOrderIntent) -> str: ...
    def amend(self, order_reference: str, intent: LiveOrderIntent) -> None: ...
    def cancel(self, order_reference: str) -> None: ...
