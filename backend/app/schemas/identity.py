from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

class Register(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    terms: Literal[True]
    privacy: Literal[True]

    @field_validator('password')
    @classmethod
    def strong(cls, v):
        if not (any((c.isupper() for c in v)) and any((c.islower() for c in v)) and any((c.isdigit() for c in v)) and any((not c.isalnum() for c in v))):
            raise ValueError('Use upper/lowercase letters, a number and a symbol')
        return v

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

class EmailInput(BaseModel):
    email: EmailStr

class TokenInput(BaseModel):
    token: str

class Reset(TokenInput):
    password: str = Field(min_length=12, max_length=128)
    _strong = field_validator('password')(Register.strong.__func__)

class Profile(BaseModel):
    name: str = Field(min_length=2, max_length=100)

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=12, max_length=128)
    _strong = field_validator('password')(Register.strong.__func__)

class StatusInput(BaseModel):
    active: bool

class RoleInput(BaseModel):
    role: Literal['USER', 'ADMIN']
