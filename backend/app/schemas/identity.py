from typing import Literal
from datetime import date
import re
from pydantic import BaseModel, EmailStr, Field, field_validator

class PersonalDetails(BaseModel):
    gender: Literal['female', 'male', 'non_binary', 'prefer_not_to_say'] | None = None
    date_of_birth: date | None = None
    mobile: str | None = None

    @field_validator('name', check_fields=False)
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Full name must contain at least two characters')
        return value

    @field_validator('date_of_birth')
    @classmethod
    def valid_birth(cls, value):
        if value and not date(1900, 1, 1) <= value <= date.today():
            raise ValueError('Enter a birth date between 1900 and today')
        return value

    @field_validator('mobile')
    @classmethod
    def valid_mobile(cls, value):
        if value and not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
            raise ValueError('Use international format, for example +919876543210')
        return value or None

class Register(PersonalDetails):
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
    totp_code: str | None = None
    email: EmailStr
    password: str = Field(max_length=128)

class EmailInput(BaseModel):
    email: EmailStr

class TokenInput(BaseModel):
    token: str

class Reset(TokenInput):
    password: str = Field(min_length=12, max_length=128)
    _strong = field_validator('password')(Register.strong.__func__)

class Profile(PersonalDetails):
    name: str = Field(min_length=2, max_length=100)

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=12, max_length=128)
    _strong = field_validator('password')(Register.strong.__func__)

class StatusInput(BaseModel):
    active: bool

class RoleInput(BaseModel):
    role: Literal['USER', 'ADMIN']

class Preferences(BaseModel):
    theme: Literal['light', 'carbon_black', 'royal_blue']

class EmailChange(BaseModel):
    email: EmailStr
    current_password: str = Field(max_length=128)
