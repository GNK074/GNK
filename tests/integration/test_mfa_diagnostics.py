import json
from sqlalchemy import select
from test_auth import client
from test_profile_settings import signed_in
from app import main as m
from app.models.identity import User
from app.security.encryption import encrypt
from app.security.mfa_diagnostics import diagnose_mfa


def test_mfa_diagnosis_is_read_only_and_never_exposes_secrets(client):
    c,h=signed_in(client)
    secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
    encrypted=encrypt(secret)
    stamp=1234567890
    with m.DB() as s:
        u=s.scalar(select(User).where(User.email=='trader@example.com'))
        u.mfa_secret=encrypted;u.mfa_enabled=True;u.mfa_counter=stamp//30+10
        s.commit()
        before=u.mfa_counter
        result=diagnose_mfa(s,'trader@example.com',stamp)
        assert result['counter_ahead_of_acceptance_window']
        assert result['setup_key_readable'] and result['mfa_enabled']
        assert result['seconds_until_unused_time_step']>30
        encoded=json.dumps(result)
        assert all(value not in encoded for value in [secret,encrypted,'trader@example.com',str(before)])
        s.expire_all()
        assert s.get(User,u.id).mfa_counter==before
        u=s.get(User,u.id);u.mfa_secret='invalid-ciphertext';s.commit()
        assert not diagnose_mfa(s,'trader@example.com',stamp)['setup_key_readable']
        assert not diagnose_mfa(s,'missing@example.com',stamp)['account_found']
