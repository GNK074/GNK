import json
from cryptography.fernet import Fernet, MultiFernet
from app.core.config import settings

def cipher():
    keys = [settings.field_encryption_key.get_secret_value()] + [x for x in settings.field_encryption_previous_keys.get_secret_value().split(',') if x]
    return MultiFernet([Fernet(x.encode()) for x in keys])

def encrypt(value):
    return cipher().encrypt(value.encode()).decode()

def decrypt(value):
    return cipher().decrypt(value.encode()).decode()

def seal_credentials(user_id, account_id, data):
    return encrypt(json.dumps(dict(user_id=user_id, account_id=account_id, data=data)))

def open_credentials(user_id, account_id, value):
    record = json.loads(decrypt(value))
    if record['user_id'] != user_id or record['account_id'] != account_id:
        raise ValueError('Credential ownership mismatch')
    return record['data']
