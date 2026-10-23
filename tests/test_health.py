from fastapi.testclient import TestClient

from app.main import create_app


def test_root_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_health_and_ready_endpoints():
    app = create_app()
    client = TestClient(app)
    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'

    ready = client.get('/ready')
    assert ready.status_code == 200
    assert 'ready' in ready.json()


def test_wildcard_cors_allows_any_origin_without_credentials():
    client = TestClient(create_app())
    response = client.options(
        '/health',
        headers={
            'Origin': 'https://any-website.example',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == '*'
    assert 'access-control-allow-credentials' not in response.headers
