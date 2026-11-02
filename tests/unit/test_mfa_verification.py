from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.security import mfa
from app.security.encryption import encrypt

SECRET='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'

@pytest.mark.parametrize('timestamp,expected',[(59,'287082'),(1111111109,'081804'),(1111111111,'050471'),(1234567890,'005924'),(2000000000,'279037'),(20000000000,'353130')])
def test_sha1_rfc6238_vectors(timestamp,expected):
    assert mfa.totp(SECRET,timestamp//30)==expected


def test_replay_wrong_code_and_next_code_have_distinct_outcomes(monkeypatch):
    tick=1234567890
    monkeypatch.setattr(mfa.time,'time',lambda:tick)
    user=SimpleNamespace(mfa_secret=encrypt(SECRET),mfa_counter=-1)
    code=mfa.totp(SECRET,tick//30)
    mfa.verify_totp(user,code[:3]+' '+code[3:])
    used=user.mfa_counter
    with pytest.raises(HTTPException,match='already been used'):
        mfa.verify_totp(user,code)
    assert user.mfa_counter==used
    wrong=next(f'{n:06d}' for n in range(100) if f'{n:06d}' not in {mfa.totp(SECRET,tick//30+i) for i in [-1,0,1]})
    with pytest.raises(HTTPException,match='incorrect or expired'):
        mfa.verify_totp(user,wrong)
    assert user.mfa_counter==used
    tick+=30
    mfa.verify_totp(user,mfa.totp(SECRET,tick//30))
    assert user.mfa_counter>used

@pytest.mark.parametrize('code',['','12345','abcdef','１２３４５６'])
def test_malformed_codes_do_not_change_counter(code):
    user=SimpleNamespace(mfa_secret=encrypt(SECRET),mfa_counter=-1)
    with pytest.raises(HTTPException,match='current 6-digit code'):
        mfa.verify_totp(user,code)
    assert user.mfa_counter==-1
