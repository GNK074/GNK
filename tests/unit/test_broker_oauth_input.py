from app.brokers.gateway import ConnectInput


def test_oauth_request_masks_credentials():
    request = ConnectInput(mode='INDIVIDUAL', client_id='private-client', client_secret='private-secret')

    assert 'private-client' not in repr(request)
    assert 'private-secret' not in request.model_dump_json()
    assert request.client_id.get_secret_value() == 'private-client'
    assert request.client_secret.get_secret_value() == 'private-secret'
    assert ConnectInput().client_secret.get_secret_value() == ''
