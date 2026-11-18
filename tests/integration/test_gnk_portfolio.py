from decimal import Decimal

from sqlalchemy import delete

from app.execution.paper import PaperMark
from app.main import DB
from test_auth import client
from test_gnk_paper import BASE, login, payload, strategy, traders


def test_portfolio_reports_owned_holdings_funds_and_profit(traders):
    c = traders
    path = BASE + '/portfolio'
    assert c.get(path).status_code == 401
    headers = login(c, 0)
    order = payload(strategy(c, headers))
    symbol = order['symbol']
    assert c.post(BASE + '/orders', headers=headers, json=order).status_code == 201
    pending = c.get(path).json()
    assert pending['holdings'] == []
    assert pending['orders'][0]['status'] == 'open'
    assert Decimal(pending['funds']['reserved']) == 200

    for sequence, price in ((1, 95), (2, 105)):
        assert c.post(BASE + '/replay/price', headers=headers, json={
            'symbol': symbol, 'sequence': sequence, 'price': price,
        }).status_code == 200

    snapshot = c.get(path).json()
    holding, = snapshot['holdings']
    assert holding['symbol'] == symbol
    assert holding['quantity'] == 2
    assert Decimal(snapshot['funds']['used']) == 190
    assert Decimal(snapshot['funds']['reserved']) == 0
    assert Decimal(snapshot['pnl']['marked_value']) == 210
    assert Decimal(snapshot['pnl']['unrealized']) == 20
    assert Decimal(snapshot['pnl']['total']) == 20

    assert c.post(BASE + f'/positions/{holding["id"]}/square-off', headers=headers).status_code == 200
    closed = c.get(path).json()
    assert closed['holdings'] == []
    assert closed['pnl']['by_symbol'][0]['state'] == 'closed'
    assert Decimal(closed['pnl']['realized']) == 20
    assert Decimal(closed['pnl']['unrealized']) == 0

    login(c, 1)
    other = c.get(path).json()
    assert other['holdings'] == other['orders'] == other['pnl']['by_symbol'] == []


def test_portfolio_leaves_unpriced_valuation_unknown(traders):
    c = traders
    headers = login(c, 0)
    order = payload(strategy(c, headers))
    assert c.post(BASE + '/orders', headers=headers, json=order).status_code == 201
    assert c.post(BASE + '/replay/price', headers=headers, json={
        'symbol': order['symbol'], 'sequence': 1, 'price': 95,
    }).status_code == 200
    with DB() as session:
        session.execute(delete(PaperMark))
        session.commit()
    pnl = c.get(BASE + '/portfolio').json()['pnl']
    assert pnl['unpriced_holdings'] == 1
    assert pnl['marked_value'] is pnl['unrealized'] is pnl['total'] is None
    assert Decimal(pnl['realized']) == 0
