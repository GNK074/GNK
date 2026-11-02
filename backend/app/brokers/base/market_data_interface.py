from typing import Protocol,AsyncIterator
class MarketDataAdapter(Protocol):
    def subscribe(self,authorized_instruments:tuple[str,...])->AsyncIterator[dict]: ...
# Contract only. Licensing and per-account entitlements must be verified first.
