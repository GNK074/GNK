"""Real PostgreSQL RLS verification, enabled only against an isolated test DB."""
import os,subprocess,sys,uuid
from pathlib import Path
import pytest
from sqlalchemy.engine import make_url

@pytest.mark.skipif(not os.getenv('GNK_TEST_POSTGRES_URL'),reason='Requires isolated PostgreSQL CI service')
def test_postgres_rls_and_composite_ownership_constraints():
    import psycopg
    root=Path(__file__).resolve().parents[2]
    raw=os.environ['GNK_TEST_POSTGRES_URL']
    env={**os.environ,'DATABASE_URL':raw.replace('postgresql://','postgresql+psycopg://'),'APP_ENV':'testing','PYTHONPATH':str(root/'backend')}
    result=subprocess.run([sys.executable,'-m','alembic','-c',str(root/'backend/alembic.ini'),'upgrade','head'],env=env,cwd=root,capture_output=True)
    assert result.returncode==0,'PostgreSQL test migration failed (output suppressed to avoid connection information)'
    ids=[str(uuid.uuid4()) for _ in range(3)];sids=[str(uuid.uuid4()) for _ in range(3)]
    with psycopg.connect(raw,autocommit=True) as conn:
        conn.execute("CREATE ROLE gnk_rls_test NOLOGIN NOSUPERUSER NOBYPASSRLS")
        conn.execute('GRANT USAGE ON SCHEMA public TO gnk_rls_test')
        conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO gnk_rls_test')
        login_ids=[str(uuid.uuid4()) for _ in ids]
        for i,(uid,sid) in enumerate(zip(ids,sids)):
            conn.execute("INSERT INTO users(id,email,name,password,verified,active,role,created) VALUES(%s,%s,'RLS test','unused',true,true,'USER',now())",(uid,f'{uid}@example.com'))
            conn.execute("INSERT INTO strategies(id,user_id,name,approved,created_at) VALUES(%s,%s,'research',false,now())",(sid,uid))
            conn.execute("INSERT INTO user_sessions(id,user_id,refresh_hash,csrf,expires,revoked,agent,created,mfa_complete) VALUES(%s,%s,%s,'csrf',now()+interval '1 day',false,'test',now(),true)",(login_ids[i],uid,str(uuid.uuid4())))
        for i,uid in enumerate(ids):
            with conn.transaction():
                conn.execute('SET LOCAL ROLE gnk_rls_test')
                conn.execute("SELECT set_config('app.user_id',%s,true)",(uid,))
                rows=conn.execute('SELECT user_id FROM strategies').fetchall()
                assert rows==[(uid,)]
                changed=conn.execute('UPDATE strategies SET name=%s WHERE id=%s',('intrusion',sids[(i+1)%3])).rowcount
                assert changed==0
                conn.execute("INSERT INTO disclosure_acknowledgments(id,user_id,session_id,disclosure_id,disclosure_version,content_sha256,period_key,acknowledged_at,created_at) VALUES(%s,%s,%s,'risk','test','hash','window',now(),now())",(str(uuid.uuid4()),uid,login_ids[i]))
                assert conn.execute('SELECT user_id FROM disclosure_acknowledgments').fetchall()==[(uid,)]
                assert conn.execute("UPDATE disclosure_acknowledgments SET disclosure_version='forged'").rowcount==0
                assert conn.execute('DELETE FROM disclosure_acknowledgments').rowcount==0
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE gnk_rls_test')
                    conn.execute("SELECT set_config('app.user_id',%s,true)",(uid,))
                    conn.execute("INSERT INTO disclosure_acknowledgments(id,user_id,session_id,disclosure_id,disclosure_version,content_sha256,period_key,acknowledged_at,created_at) VALUES(%s,%s,%s,'risk','forged','hash','window',now(),now())",(str(uuid.uuid4()),uid,login_ids[(i+1)%3]))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE gnk_rls_test')
                    conn.execute("SELECT set_config('app.user_id',%s,true)",(uid,))
                    conn.execute("INSERT INTO strategies(id,user_id,name,approved,created_at) VALUES(%s,%s,'intrusion',false,now())",(str(uuid.uuid4()),ids[(i+1)%3]))
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE gnk_rls_test')
                    conn.execute("SELECT set_config('app.user_id',%s,true)",(uid,))
                    conn.execute("INSERT INTO orders(id,user_id,strategy_id,symbol,side,quantity,price,mode,status,idempotency_key,request_hash,realized_pnl,created_at) VALUES(%s,%s,%s,'TEST','BUY',1,1,'paper','filled',%s,'hash',0,now())",(str(uuid.uuid4()),uid,sids[(i+1)%3],str(uuid.uuid4())))
        # A new transaction has no inherited tenant identity and sees no records.
        with conn.transaction():
            conn.execute('SET LOCAL ROLE gnk_rls_test')
            assert conn.execute('SELECT count(*) FROM strategies').fetchone()[0]==0
