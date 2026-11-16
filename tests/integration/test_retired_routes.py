from test_auth import client


def test_retired_routes_return_not_found(client):
    http, _ = client
    paths = (
        '/api/v1/dhan/status',
        '/api/v1/dhan/instruments',
        '/api/v1/live/readiness',
        '/api/v1/brokers/connections',
        '/api/v1/strategies',
        '/api/v1/tradedetails/orders',
    )
    for path in paths:
        assert http.get(path).status_code == 404, path
    for path in ('/api/v1/live/orders', '/api/v1/paper/orders'):
        assert http.post(path, json={}).status_code in (404, 405), path
