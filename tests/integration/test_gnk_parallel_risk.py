from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.execution import paper, paper_risk
from app.main import Base
from app.models.identity import User
from app.models.trading import Order, RiskConfiguration, Strategy


def test_rule_groups_overlap_and_preserve_rejection_priority(monkeypatch):
    snapshot = paper_risk.RiskSnapshot(
        order=paper_risk.OrderExposure('TEST', 'BUY', 5, Decimal('100')),
        positions=(), pending=(), daily_order_count=20, daily_loss=Decimal('300'),
        max_quantity=4, max_order_value=Decimal('400'), max_daily_orders=20,
        max_daily_loss=Decimal('200'), max_positions=0, paper_collateral=Decimal('100'),
    )
    barrier = Barrier(3)

    def synchronized(check):
        def evaluate(value):
            barrier.wait(timeout=5)
            return check(value)
        return evaluate

    for name in ('order_limits', 'position_limits', 'collateral_limits'):
        monkeypatch.setattr(paper_risk, name, synchronized(getattr(paper_risk, name)))

    assert paper_risk.rejection_reason(snapshot) == 'Order exceeds personal risk limits'


def test_competing_orders_cannot_both_reserve_the_same_collateral(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "risk.sqlite"}')
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            user = User(name='Risk case', email='risk-case@example.com', password='unused')
            session.add(user)
            session.flush()
            trading_strategy = Strategy(user_id=user.id, name='Risk case strategy')
            session.add_all([trading_strategy, RiskConfiguration(user_id=user.id, paper_collateral=150)])
            session.flush()
            user_id, strategy_id = user.id, trading_strategy.id
            session.commit()

        start = Barrier(2)

        def place(key):
            data = paper.LimitOrder(strategy_id=strategy_id, symbol='TEST', side='BUY',
                                    quantity=1, price=Decimal('100'), idempotency_key=key)
            with Session(engine) as session:
                start.wait(timeout=5)
                try:
                    return paper.place(data, SimpleNamespace(id=user_id), session)['status']
                except HTTPException as error:
                    assert error.status_code == 422
                    return error.detail

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(place, ('first-order', 'second-order')))
        assert sorted(results) == ['Insufficient paper collateral', 'open']
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(Order)) == 1
    finally:
        engine.dispose()
