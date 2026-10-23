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
