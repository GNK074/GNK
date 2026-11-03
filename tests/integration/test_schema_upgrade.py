"""Reproduce stale production schema and verify the actual additive upgrade."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from app import main as m
from app.database.readiness import check_schema, SchemaNotReady
from app.api import auth, health
from app.services import accounts


def test_old_schema_fails_readiness_then_migration_restores_registration(tmp_path, monkeypatch):
    root=Path(__file__).resolve().parents[2]
    url='sqlite:///'+(tmp_path/'upgrade.db').as_posix()
    env={**os.environ,'DATABASE_URL':url,'APP_ENV':'testing','STARTUP_CONNECTIVITY_CHECK':'false','PYTHONPATH':str(root/'backend')}
    command=[sys.executable,'-m','alembic','-c',str(root/'backend/alembic.ini'),'upgrade']
    subprocess.run(command+['0002'],cwd=root,env=env,check=True,capture_output=True)
    engine=create_engine(url,connect_args={'check_same_thread':False})
    with engine.begin() as c:
        c.execute(text("INSERT INTO users(id,email,name,password,verified,active,role,mfa_enabled,mfa_counter,created) VALUES('existing','existing@example.com','Existing User','preserved-hash',1,1,'USER',0,-1,'2026-01-01')"))
    with engine.connect() as c:
        with pytest.raises(SchemaNotReady,match='Database revisions: 0002; image requires:'):
            check_schema(c)
    old_bind=m.DB.kw['bind']
    m.DB.configure(bind=engine)
    monkeypatch.setattr(auth,'limit',lambda *args:None)
    monkeypatch.setattr(health.cache,'ping',lambda:True)
    mail=[]
    monkeypatch.setattr(accounts,'send_email',lambda email,title,link:mail.append(link))
    try:
        with TestClient(m.app) as client:
            assert client.get('/api/v1/health').status_code==503
            subprocess.run(command+['head'],cwd=root,env=env,check=True,capture_output=True)
            with engine.connect() as c:
                check_schema(c)
                assert c.execute(text("SELECT password FROM users WHERE id='existing'")).scalar()=='preserved-hash'
            assert client.get('/api/v1/health').status_code==200
            data={'name':'New Trader','email':'new@example.com','password':'StrongPassword!123','gender':'female','date_of_birth':'1990-05-12','mobile':'+919876543210','terms':True,'privacy':True}
            assert client.post('/api/v1/auth/register',json=data).status_code==202
            token=mail[-1].split('token=')[1]
            assert client.post('/api/v1/auth/verify-email',json={'token':token}).status_code==200
            assert client.post('/api/v1/auth/login',json={'email':data['email'],'password':data['password']}).status_code==200
            user=client.get('/api/v1/users/me').json()['user']
            assert user['gender']==data['gender'] and user['mobile']==data['mobile']
    finally:
        m.DB.configure(bind=old_bind)
        engine.dispose()


def test_revision_stamp_cannot_hide_a_missing_column(tmp_path):
    engine=create_engine('sqlite://')
    m.Base.metadata.create_all(engine)
    cfg=Config(str(Path(__file__).resolve().parents[2]/'backend/alembic.ini'))
    head=ScriptDirectory.from_config(cfg).get_current_head()
    with engine.begin() as c:
        c.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)'))
        c.execute(text('INSERT INTO alembic_version VALUES (:head)'),{'head':head})
        c.execute(text('ALTER TABLE users DROP COLUMN gender'))
    with engine.connect() as c:
        with pytest.raises(SchemaNotReady,match='Missing columns in users: gender'): check_schema(c)
    engine.dispose()
