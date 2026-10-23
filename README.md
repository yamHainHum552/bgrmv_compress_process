# Product Image Background Removal & Compression API

A FastAPI service for removing backgrounds from product images, compressing output files, and processing images in a single request.

## Features

- Background removal using `rembg` with a reusable model session
- JPEG/PNG/WebP upload support
- Resize-preserving image optimization
- Solid-color replacement background support
- Transparent PNG output by default
- Binary image responses with content headers
- Structured health and readiness checks
- Docker-ready deployment
- Testable service layer with mocked inference functions

## Prerequisites

- Python 3.12+
- pip
- Optional: Docker Desktop / Docker Engine

## Windows PowerShell setup

```powershell
cd "C:\Users\Acer\OneDrive\Desktop\Python\removebackgroundapi"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Linux/macOS setup

```bash
cd /path/to/removebackgroundapi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment configuration

The application reads settings from environment variables or `.env`.

`CORS_ORIGINS=*` allows browser requests from any website. For a private or production deployment, prefer a comma-separated list of trusted origins, for example `https://shop.example.com,https://admin.example.com`. The wildcard mode disables credentialed cross-origin requests; this API does not require browser cookies. CORS is a browser policy, not authentication or abuse protection.

```env
APP_ENV=development
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
MAX_UPLOAD_SIZE_MB=20
MAX_IMAGE_PIXELS=50000000
MAX_IMAGE_DIMENSION=8192
MODEL_NAME=u2netp
INFERENCE_CONCURRENCY=2
THREAD_POOL_SIZE=4
CORS_ORIGINS=*
DEFAULT_OUTPUT_FORMAT=png
DEFAULT_IMAGE_QUALITY=85
```

## API endpoints

### Service metadata

- `GET /` returns basic service information
- `GET /health` returns service health
- `GET /ready` validates the model session is initialized
- `GET /api/v1/info` returns configured limits and supported formats

### Background removal

```bash
curl -X POST "http://localhost:8000/api/v1/images/remove-background" \
  -F "file=@/path/to/product.png" \
  -F "background_color=#FFFFFF"
```

### Compression

```bash
curl -X POST "http://localhost:8000/api/v1/images/compress" \
  -F "file=@/path/to/product.png" \
  -F "output_format=webp" \
  -F "quality=80" \
  -F "max_width=1200"
```

### Combined processing

```bash
curl -X POST "http://localhost:8000/api/v1/images/process" \
  -F "file=@/path/to/product.png" \
  -F "output_format=jpeg" \
  -F "quality=85" \
  -F "max_width=1400" \
  -F "background_color=#FFFFFF" \
  -F "remove_background=true"
```

### Python example

```python
import io
from PIL import Image

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

with Image.new('RGB', (100, 100), 'red') as img:
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    response = client.post(
        '/api/v1/images/process',
        files={'file': ('product.png', buffer.getvalue(), 'image/png')},
        data={'output_format': 'png', 'remove_background': 'true', 'quality': 85},
    )
    print(response.status_code)
    print(response.headers.get('content-type'))
```

## Model initialization and first run

The service uses `rembg` and loads its model once per worker process. `u2netp` is the default model, and rembg will download it on first use if it is not already cached. Model cache directories are shared according to the operating system environment and can be retained between container restarts.

## Running tests

```bash
pytest
```

## Running Docker

```bash
docker build -t product-image-api .
docker run --rm -p 8000:8000 product-image-api
```

or

```bash
docker compose up --build
```

## Troubleshooting

### ONNX Runtime errors

- Reinstall the package in a clean environment.
- Ensure you are using a compatible Python version.
- On Linux, install `libgomp1` and `libglib2.0-0` as needed.
- Rebuild the container after dependency changes.

### rembg model download issues

- Ensure the environment can reach the model distribution endpoint.
- Re-run the app after the model cache is available.
- Check network access if the model is not already cached.

## Performance tuning

- Keep `INFERENCE_CONCURRENCY` low enough to avoid RAM spikes.
- Use a moderate value for `THREAD_POOL_SIZE` on CPU-only hosts.
- Avoid running multiple Uvicorn workers when memory is constrained.
- When memory is a limiting factor, prefer one worker per CPU and a lower concurrency setting.

## CPU vs GPU guidance

- The default configuration is CPU-only, which works on standard machines.
- For GPU acceleration, install a CUDA-capable ONNX Runtime build and set the runtime to the GPU execution provider.
- The exact installation steps depend on the CUDA version and system driver support.
- Do not assume GPU acceleration is available in all environments.

## OpenAPI docs

FastAPI automatically exposes:

- `/docs`
- `/redoc`
- `/openapi.json`

## Notes on concurrency and memory

This service intentionally keeps AI inference off the async event loop by using a thread pool and explicit inference limits. This avoids overwhelming the event loop and prevents unbounded memory usage under concurrent image uploads.

Each Uvicorn worker process creates its own in-memory model session. On systems with limited RAM, run fewer workers and lower the inference concurrency to keep memory usage stable.
