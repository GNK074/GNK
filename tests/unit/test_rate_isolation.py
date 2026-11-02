from types import SimpleNamespace
import pytest,redis
from fastapi import HTTPException
from app.security import authentication as security
class Counter:
    def __init__(self):self.values={}
    def eval(self,script,n,key,ttl):
        assert ttl==900 and 'EXPIRE' in script
        self.values[key]=self.values.get(key,0)+1
        return self.values[key]

def test_shared_proxy_does_not_merge_user_auth_limits(monkeypatch):
    cache=Counter();monkeypatch.setattr(security,'cache',cache)
    request=SimpleNamespace(client=SimpleNamespace(host='proxy-address'))
    for _ in range(20):security.limit(request,'login','user-a@example.com')
    with pytest.raises(HTTPException) as failure:security.limit(request,'login','user-a@example.com')
    assert failure.value.status_code==429
    security.limit(request,'login','user-b@example.com')
    assert all('user-a@example.com' not in key for key in cache.values)

def test_rate_limiter_fails_closed(monkeypatch):
    class Failed:
        def eval(self,*args):raise redis.RedisError()
    monkeypatch.setattr(security,'cache',Failed())
    with pytest.raises(HTTPException) as failure:security.limit(SimpleNamespace(client=SimpleNamespace(host='x')),'login','user')
    assert failure.value.status_code==503
