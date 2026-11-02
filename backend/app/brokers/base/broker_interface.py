from dataclasses import dataclass,field
from datetime import datetime
@dataclass
class BrokerTokens:
    access_token:str=field(repr=False)
    account_identifier:str
    refresh_token:str | None=field(default=None,repr=False)
    expires_at:datetime | None=None
