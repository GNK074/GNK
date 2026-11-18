from test_auth import client
from test_gnk_paper import login, traders

BASE = '/api/v1/gnk/live'


def test_live_api_fails_closed_without_reading_or_writing_paper_orders(traders):
    c = traders
    assert c.get(BASE + '/status').status_code == 401
    headers = login(c, 0)
    status = c.get(BASE + '/status').json()
    assert status['mode'] == 'LIVE'
    assert not status['enabled']
    preexisting = c.get('/api/v1/gnk/paper/orders').json()
    order = {
        'client_order_id': 'gnk-2026-11-18', 'instrument_id': 'GNK-TEST', 'side': 'BUY',
        'quantity': 1, 'limit_price': '100', 'confirm_real_money': True,
    }
    assert c.post(BASE + '/orders', headers=headers, json={
        **order, 'confirm_real_money': False,
    }).status_code == 422
    rejected = c.post(BASE + '/orders', headers=headers, json=order)
    assert rejected.status_code == 503
    assert rejected.json()['detail'] == status['blocker']
    assert c.get('/api/v1/gnk/paper/orders').json() == preexisting
