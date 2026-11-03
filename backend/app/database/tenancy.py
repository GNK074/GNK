from sqlalchemy import event, text
from sqlalchemy.orm import Session

def set_context(session, user_id='', callback_hash=''):
    session.info['tenant_user_id'] = user_id
    session.info['callback_state_hash'] = callback_hash
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text("SELECT set_config('app.user_id', :uid, true), set_config('app.callback_state_hash', :state, true)"), {'uid': user_id, 'state': callback_hash})

@event.listens_for(Session, 'after_begin')
def apply_transaction_context(session, transaction, connection):
    if connection.dialect.name == 'postgresql':
        connection.execute(text("SELECT set_config('app.user_id', :uid, true), set_config('app.callback_state_hash', :state, true), set_config('app.market_worker', :worker, true)"), {'uid': session.info.get('tenant_user_id', ''), 'state': session.info.get('callback_state_hash', ''), 'worker': 'true' if session.info.get('market_worker') else 'false'})


def set_market_worker(session):
    session.info['market_worker'] = True
    if session.get_bind().dialect.name == 'postgresql':
        session.execute(text("SELECT set_config('app.market_worker', 'true', true)"))
