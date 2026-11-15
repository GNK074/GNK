"""Dhan pilot requests use fixtures and never contact a real broker."""
from datetime import timedelta
from types import SimpleNamespace

from test_auth import client
from test_multi_user import login, three
from app import main as app
from app.brokers.dhan import pilot
from app.core.config import now
from app.models.trading import BrokerAccount, BrokerCredential


def test_pilot_verifies_reads_and_disconnects_without_persisting_credentials(three, monkeypatch):
    browser, _, _ = three
    headers = login(browser, 0)
    monkeypatch.setattr(pilot, "limit", lambda *args: None)
    monkeypatch.setattr(pilot.settings, "broker_egress_ip", "192.0.2.1")

    class Client:
        def __init__(self, client_id, token):
            assert client_id == "123456" and token == "fixture-token"
        def read(self, kind):
            assert kind == "holdings"
            return [{"tradingSymbol": "TEST", "totalQty": 2, "avgCostPrice": 100}]
        def ip_whitelist_matches(self, ip):
            return ip == "192.0.2.1"

    monkeypatch.setattr(pilot, "DhanClient", Client)
    monkeypatch.setattr(pilot.DhanVerifier, "validate", lambda self, data: SimpleNamespace(
        account_identifier=data["client_id"], expires_at=now() + timedelta(hours=1)
    ))
    body = {"client_id": "123456", "access_token": "fixture-token", "owns_account": True}
    assert browser.post("/api/v1/dhan/pilot/session", json=body).status_code == 403
    response = browser.post("/api/v1/dhan/pilot/session", json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["connected"] and response.headers["cache-control"] == "no-store"
    assert "fixture-token" not in response.text and "123456" not in response.text
    assert browser.get("/api/v1/dhan/pilot/portfolio/holdings").json()["data"][0]["symbol"] == "TEST"
    assert browser.get("/api/v1/dhan/pilot/ip").json()["data"]["state"] == "MATCH"
    with app.DB() as session:
        assert session.query(BrokerAccount).count() == 3
        assert session.query(BrokerCredential).count() == 3
    saved_cookies = list(browser.cookies.jar)
    login(browser, 1)
    assert not browser.get("/api/v1/dhan/pilot/session").json()["connected"]
    assert browser.get("/api/v1/dhan/pilot/portfolio/holdings").status_code == 409
    browser.cookies.clear()
    for cookie in saved_cookies:
        browser.cookies.jar.set_cookie(cookie)
    assert browser.delete("/api/v1/dhan/pilot/session", headers=headers).status_code == 200
    assert not browser.get("/api/v1/dhan/pilot/session").json()["connected"]


def test_pilot_rejects_unverified_identity(three, monkeypatch):
    browser, _, _ = three
    headers = login(browser, 0)
    monkeypatch.setattr(pilot, "limit", lambda *args: None)
    monkeypatch.setattr(pilot.DhanVerifier, "validate", lambda self, data: SimpleNamespace(
        account_identifier="someone-else", expires_at=now() + timedelta(hours=1)
    ))
    response = browser.post("/api/v1/dhan/pilot/session", headers=headers, json={
        "client_id": "123456", "access_token": "fixture-token", "owns_account": True
    })
    assert response.status_code == 422
    assert not browser.get("/api/v1/dhan/pilot/session").json()["connected"]
