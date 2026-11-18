from decimal import Decimal

import pytest

from app.main import DB, hasher
from app.models.identity import User
from test_auth import client

BASE = '/api/v1/gnk/paper'


@pytest.fixture
def traders(client):
    c, _ = client
    password = hasher.hash('StrongPassword!123')
    with DB() as session:
        for index in range(2):
            session.add(User(name=f'Trader {index}', email=f'paper{index}@example.com',
                             password=password, verified=True))
        session.commit()
    return c


def login(c, index):
    response = c.post('/api/v1/auth/login', json={
        'email': f'paper{index}@example.com', 'password': 'StrongPassword!123',
    })
    assert response.status_code == 200, response.text
    headers = {'X-CSRF-Token': response.json()['csrf_token']}
    disclosure = c.get('/api/v1/compliance/disclosure').json()
    response = c.post('/api/v1/compliance/disclosure/acknowledge', headers=headers, json={
        'disclosure_id': disclosure['id'], 'disclosure_version': disclosure['version'],
        'content_sha256': disclosure['content_sha256'], 'acknowledged': True,
    })
    assert response.status_code == 200, response.text
    return headers


def strategy(c, headers):
    response = c.post(BASE + '/strategies', headers=headers, json={'name': 'Paper research'})
    assert response.status_code == 201, response.text
    return response.json()['id']


def payload(strategy_id, key='unique-order-0001'):
    return {'strategy_id': strategy_id, 'symbol': 'NIFTYTEST', 'side': 'BUY',
            'quantity': 2, 'price': '100.0000', 'idempotency_key': key}


def test_native_order_lifecycle(traders):
    c = traders
    h = login(c, 0)
    sid = strategy(c, h)
    data = payload(sid)
    assert c.put(BASE + '/risk/margin', headers=h, json={'amount': 220}).status_code == 200
    placed = c.post(BASE + '/orders', headers=h, json=data)
    assert placed.status_code == 201, placed.text
    order = placed.json()
    url = BASE + '/orders/' + order['id']
    assert order['status'] == 'open'
    assert c.post(BASE + '/orders', headers=h, json=data).json()['id'] == order['id']
    assert c.post(BASE + '/orders', headers=h, json=payload(sid, 'excess-collateral')).status_code == 422
    assert Decimal(c.get(BASE + '/risk/margin').json()['reserved']) == 200

    changed = c.patch(url, headers=h, json={'quantity': 2, 'price': 95, 'version': 1})
    assert changed.status_code == 200, changed.text
    assert c.delete(url + '?version=1', headers=h).status_code == 409
    tick = {'symbol': data['symbol'], 'sequence': 1, 'price': 96}
    assert c.post(BASE + '/replay/price', headers=h, json=tick).json()['executions'] == []
    tick.update(sequence=2, price=90)
    replayed = c.post(BASE + '/replay/price', headers=h, json=tick)
    assert replayed.status_code == 200, replayed.text
    fill, = replayed.json()['executions']
    assert fill['id'] == order['id']
    assert Decimal(fill['execution_price']) == 90
    assert c.post(BASE + '/replay/price', headers=h, json=tick).json()['duplicate']
    assert c.get(url).json()['status'] == 'filled'
    assert len(c.get(BASE + '/executions').json()) == 1
    login(c, 1)
    assert c.get(url).status_code == 404


def test_protective_and_emergency_exits(traders):
    c = traders
    h = login(c, 0)
    sid = strategy(c, h)
    data = payload(sid)

    def replay(sequence, price):
        response = c.post(BASE + '/replay/price', headers=h, json={
            'symbol': data['symbol'], 'sequence': sequence, 'price': price,
        })
        assert response.status_code == 200, response.text
        return response.json()['executions']

    assert c.post(BASE + '/orders', headers=h, json=data).status_code == 201
    replay(1, 100)
    p, = c.get(BASE + '/positions?state=open').json()
    url = BASE + '/positions/' + p['id']
    assert c.put(url + '/product', headers=h, json={'product': 'INTRADAY'}).status_code == 200
    assert c.put(url + '/protection', headers=h, json={'stop_loss': 90, 'target': 120}).status_code == 200
    pending = c.post(BASE + '/orders', headers=h, json={
        **data, 'idempotency_key': 'pending-reentry', 'price': 85,
    }).json()
    exit_fill, = replay(2, 85)
    assert exit_fill['execution_reason'] == 'STOP_LOSS'
    assert Decimal(exit_fill['realized_pnl']) == -30
    assert c.get(BASE + '/orders/' + pending['id']).json()['status'] == 'cancelled'
    assert len(c.get(BASE + '/positions?state=closed').json()) == 1

    for sequence, reason in ((3, 'SQUARE_OFF'), (4, 'EMERGENCY_EXIT')):
        order = c.post(BASE + '/orders', headers=h, json=payload(sid, 'reopen-order-' + str(sequence)))
        assert order.status_code == 201, order.text
        replay(sequence, 95)
        if reason == 'SQUARE_OFF':
            response = c.post(url + '/square-off', headers=h)
            assert response.status_code == 200, response.text
            assert response.json()['execution_reason'] == reason
        else:
            response = c.post(BASE + '/risk/emergency-exit', headers=h)
            assert response.status_code == 200, response.text
            assert response.json()['executions'][0]['execution_reason'] == reason
    assert c.get(BASE + '/positions?state=open').json() == []
    assert c.post(BASE + '/orders', headers=h, json=payload(sid, 'blocked-after-exit')).status_code == 409


def test_target_and_quantity_reservations(traders):
    c = traders
    h = login(c, 0)
    sid = strategy(c, h)
    data = payload(sid)
    assert c.post(BASE + '/orders', headers=h, json=data).status_code == 201
    tick = {'symbol': data['symbol'], 'sequence': 1, 'price': 100}
    assert c.post(BASE + '/replay/price', headers=h, json=tick).status_code == 200
    p, = c.get(BASE + '/positions?state=open').json()
    sell = {**data, 'side': 'SELL', 'price': 125, 'idempotency_key': 'working-sell-1'}
    placed = c.post(BASE + '/orders', headers=h, json=sell)
    assert placed.status_code == 201, placed.text
    sell['idempotency_key'] = 'working-sell-2'
    assert c.post(BASE + '/orders', headers=h, json=sell).status_code == 422
    url = BASE + '/orders/' + placed.json()['id']
    assert c.delete(url + '?version=1', headers=h).json()['status'] == 'cancelled'
    assert c.post(BASE + '/orders', headers=h, json=sell).status_code == 201
    position_url = BASE + '/positions/' + p['id']
    assert c.put(position_url + '/protection', headers=h, json={'target': 120}).status_code == 200
    tick.update(sequence=2, price=130)
    result = c.post(BASE + '/replay/price', headers=h, json=tick)
    assert result.status_code == 200, result.text
    exit_fill, = result.json()['executions']
    assert exit_fill['execution_reason'] == 'TARGET'
    assert Decimal(exit_fill['realized_pnl']) == 60
