from types import SimpleNamespace
import pytest
from redis.exceptions import AuthenticationError
from app.core.lifespan import check_dependencies,StartupCheckError
class Connection:
    def __init__(self,privileged=False):self.privileged=privileged
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,query):return SimpleNamespace(one=lambda:(self.privileged,False))
class Database:
    def __init__(self,privileged=False):self.privileged=privileged
    def connect(self):return Connection(self.privileged)
class Redis:
    def ping(self):return True

def test_healthy_dependencies():check_dependencies(Database(),Redis(),production=True)
def test_privileged_role_error_is_not_masked():
    with pytest.raises(StartupCheckError,match='runtime role is privileged'):check_dependencies(Database(True),Redis(),production=True)
@pytest.mark.parametrize('code,message',[('28P01','authentication failed'),('28000','authorization failed'),('3D000','does not exist'),('42501','privileges are insufficient')])
def test_postgres_errors_are_categorized_and_redacted(code,message):
    class Broken:
        def connect(self):
            error=RuntimeError('private-password-in-driver-message');error.orig=SimpleNamespace(sqlstate=code)
            raise error
    with pytest.raises(StartupCheckError,match=message) as result:check_dependencies(Broken(),Redis(),production=True)
    assert 'private-password' not in str(result.value)
def test_redis_authentication_is_distinguished():
    class Broken:
        def ping(self):raise AuthenticationError('private-redis-secret')
    with pytest.raises(StartupCheckError,match='Redis authentication failed') as result:check_dependencies(Database(),Broken(),production=True)
    assert 'private-redis-secret' not in str(result.value)
