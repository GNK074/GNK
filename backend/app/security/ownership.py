from fastapi import HTTPException
from sqlalchemy import select

def owned(s, model, record_id, user_id, lock=False):
    statement = select(model).where(model.id == record_id, model.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    record = s.scalar(statement)
    if record is None:
        raise HTTPException(404, 'Record not found')
    return record
