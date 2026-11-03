from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

def upsert(s,model,rows,keys):
    if not rows:return
    insert=pg_insert if s.get_bind().dialect.name=='postgresql' else sqlite_insert
    for offset in range(0,len(rows),500):
        chunk=rows[offset:offset+500]
        statement=insert(model).values(chunk)
        updates={key:getattr(statement.excluded,key) for key in chunk[0] if key not in (*keys,'id')}
        s.execute(statement.on_conflict_do_update(index_elements=keys,set_=updates))
