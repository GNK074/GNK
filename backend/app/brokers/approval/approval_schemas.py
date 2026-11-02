from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class EvidenceInput(BaseModel):
    reference: str = Field(min_length=10, max_length=1000)
    sha256: str = Field(pattern='^[a-f0-9]{64}$')
    expires_at: datetime

    @field_validator('reference')
    @classmethod
    def reference_scheme(cls, value):
        if not value.startswith(('https://', 'evidence://')):
            raise ValueError('Use an HTTPS or evidence registry reference')
        return value
