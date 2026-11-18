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


def test_live_risk_snapshot_is_required_and_enforces_live_limits(traders, monkeypatch):
    from dataclasses import replace
    from datetime import timedelta
    from decimal import Decimal

    from app.core.config import now, settings
    from app.execution.gnk_live import live_risk_source
    from app.execution.live_risk import LiveAccountRisk
    from app.execution.paper_risk import OrderExposure, PositionExposure
    from app.main import DB, app
    from app.models.trading import PlatformControl

    c = traders
    headers = login(c, 0)
    with DB() as session:
        session.add(PlatformControl(id='global', kill_switch=False))
        session.commit()
    monkeypatch.setattr(settings, 'trading_enabled', True)
    monkeypatch.setattr(settings, 'live_trading_enabled', True)

    class Source:
        overrides = {}

        def snapshot(self, user_id, instrument_id):
            state = LiveAccountRisk(
                user_id=user_id, instrument_id=instrument_id, as_of=now(), instrument_active=True,
                available_cash=Decimal('1000'), daily_order_count=0, daily_loss=Decimal('0'),
                positions=(), pending=(),
            )
            return replace(state, **self.overrides)

    source = Source()
    request = {
        'client_order_id': 'gnk-live-risk-test', 'instrument_id': 'GNK-TEST', 'side': 'BUY',
        'quantity': 2, 'limit_price': '100', 'confirm_real_money': True,
    }
    try:
        app.dependency_overrides[live_risk_source] = lambda: source
        cases = [
            ({'as_of': now() - timedelta(seconds=16)}, 'BUY', 503, 'A fresh, valid live risk snapshot is required'),
            ({'user_id': 'another-user'}, 'BUY', 503, 'A fresh, valid live risk snapshot is required'),
            ({'instrument_active': False}, 'BUY', 422, 'Instrument is unavailable for live trading'),
            ({'daily_order_count': 50}, 'BUY', 422, 'Daily live order limit reached'),
            ({'daily_loss': Decimal('5000')}, 'BUY', 422, 'Daily live loss limit reached'),
            ({'available_cash': Decimal('199')}, 'BUY', 422, 'Insufficient available live cash'),
            ({'positions': (PositionExposure('GNK-TEST', 99, Decimal('100')),)}, 'BUY', 422,
             'Projected live instrument exposure exceeds risk limits'),
            ({'positions': (PositionExposure('GNK-TEST', 3, Decimal('100')),),
              'pending': (OrderExposure('GNK-TEST', 'SELL', 2, Decimal('100')),)}, 'SELL', 422,
             'Insufficient unreserved live position quantity'),
            ({}, 'BUY', 503, 'GNK has no live execution connection configured.'),
        ]
        for overrides, side, code, detail in cases:
            source.overrides = overrides
            response = c.post(BASE + '/orders', headers=headers, json={**request, 'side': side})
            assert response.status_code == code, response.text
            assert response.json()['detail'] == detail

        with DB() as session:
            session.get(PlatformControl, 'global').kill_switch = True
            session.commit()
        response = c.post(BASE + '/orders', headers=headers, json=request)
        assert response.status_code == 409
        assert response.json()['detail'] == 'Emergency stop active'
        assert c.get('/api/v1/gnk/paper/orders').json() == []
    finally:
        app.dependency_overrides.pop(live_risk_source, None)
