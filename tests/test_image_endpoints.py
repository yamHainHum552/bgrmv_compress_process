import io

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _make_png_bytes(width=120, height=100, color=(255, 0, 0)) -> bytes:
    image = Image.new("RGBA", (width, height), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_info_endpoint(client):
    response = client.get('/api/v1/info')
    assert response.status_code == 200
    payload = response.json()
    assert 'png' in payload['supported_input_formats']
    assert payload['default_output_format'] == 'png'


def test_compress_endpoint_reduces_dimensions_and_returns_binary(client):
    png_bytes = _make_png_bytes(400, 200)
    response = client.post(
        '/api/v1/images/compress',
        files={'file': ('sample.png', png_bytes, 'image/png')},
        data={'output_format': 'webp', 'quality': 70, 'max_width': 200},
    )
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/webp')
    assert response.headers['x-output-width'] == '200'


def test_process_endpoint_uses_mocked_background_removal(client, monkeypatch):
    async def fake_remove(self, image):
        rgba = Image.new('RGBA', image.size, (0, 0, 0, 0))
        return rgba

    monkeypatch.setattr('app.services.background_removal.BackgroundRemovalService.remove_background_async', fake_remove)

    response = client.post(
        '/api/v1/images/process',
        files={'file': ('product.png', _make_png_bytes(200, 100), 'image/png')},
        data={'output_format': 'jpeg', 'quality': 80, 'remove_background': 'true'},
    )
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/jpeg')
    assert response.headers['x-output-format'] == 'jpeg'


def test_invalid_upload_is_rejected(client):
    response = client.post(
        '/api/v1/images/compress',
        files={'file': ('bad.txt', b'not an image', 'text/plain')},
    )
    assert response.status_code == 400
    assert 'not a valid image' in response.json()['detail'].lower()


def test_oversized_upload_is_rejected(client):
    large_bytes = b'a' * 1024 * 1024 * 100
    response = client.post(
        '/api/v1/images/compress',
        files={'file': ('huge.png', large_bytes, 'image/png')},
    )
    assert response.status_code == 400
    assert 'maximum allowed size' in response.json()['detail'].lower()


def test_invalid_quality_rejected(client):
    response = client.post(
        '/api/v1/images/process',
        files={'file': ('product.png', _make_png_bytes(80, 80), 'image/png')},
        data={'quality': '0'},
    )
    assert response.status_code == 400
    assert 'quality' in response.json()['detail'].lower()
