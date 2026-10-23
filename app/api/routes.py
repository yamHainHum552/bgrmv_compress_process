from __future__ import annotations

import time
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.core.config import get_settings
from app.schemas.responses import HealthResponse, InfoResponse, ReadyResponse, ServiceInfoResponse
from app.services.background_removal import BackgroundRemovalService
from app.services.compression import resize_image_with_aspect_ratio
from app.services.image_pipeline import ImagePipeline
from app.utils.validation import decode_image, normalize_format, parse_background_color, sanitize_filename, validate_upload_size

api_router = APIRouter()
settings = get_settings()


def get_background_service(request: Request) -> BackgroundRemovalService:
    return request.app.state.background_removal_service


def _encode_image_bytes(
    image,
    *,
    output_format: str,
    quality: int,
    background_color: str | None,
) -> tuple[bytes, str]:
    try:
        normalized_format = normalize_format(output_format)
        background_rgb = parse_background_color(background_color) if background_color else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    buffer = BytesIO()
    if normalized_format == "jpeg":
        if image.mode in {"RGBA", "LA", "P"}:
            from PIL import Image as PILImage

            if background_rgb is None:
                background_rgb = (255, 255, 255)
            background = PILImage.new("RGBA", image.size, background_rgb + (255,))
            composite = PILImage.alpha_composite(background, image.convert("RGBA"))
            composite.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        else:
            image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    elif normalized_format == "webp":
        image.save(buffer, format="WEBP", quality=quality, method=6, lossless=False)
    else:
        if image.mode not in {"RGBA", "RGB", "L", "P"}:
            image = image.convert("RGBA")
        image.save(buffer, format="PNG", optimize=True)

    return buffer.getvalue(), normalized_format


@api_router.get("/", response_model=ServiceInfoResponse, tags=["meta"])
async def root() -> ServiceInfoResponse:
    return ServiceInfoResponse(name=settings.app_name, version="1.0.0", status="ok")


@api_router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/ready", response_model=ReadyResponse, tags=["meta"])
async def ready(request: Request) -> ReadyResponse:
    service = get_background_service(request)
    try:
        service.initialize()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not service.ready:
        raise HTTPException(status_code=503, detail="The background-removal model is not initialized.")
    return ReadyResponse(status="ready", ready=True, model_name=settings.model_name)


@api_router.get("/api/v1/info", response_model=InfoResponse, tags=["meta"])
async def info() -> InfoResponse:
    return InfoResponse(
        supported_input_formats=["png", "jpeg", "webp"],
        supported_output_formats=["png", "jpeg", "webp"],
        max_upload_size_mb=settings.max_upload_size_mb,
        max_image_pixels=settings.max_image_pixels,
        max_image_dimension=settings.max_image_dimension,
        default_output_format=settings.default_output_format,
        default_image_quality=settings.default_image_quality,
        inference_concurrency=settings.inference_concurrency,
        thread_pool_size=settings.thread_pool_size,
    )


async def _read_and_validate_upload(file: UploadFile) -> tuple[bytes, object]:
    try:
        original_bytes = await file.read()
        validate_upload_size(len(original_bytes), settings.max_upload_size_bytes)
        image = decode_image(
            original_bytes,
            max_pixels=settings.max_image_pixels,
            max_dimension=settings.max_image_dimension,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return original_bytes, image


@api_router.post("/api/v1/images/remove-background", tags=["images"])
async def remove_background(
    request: Request,
    file: Annotated[UploadFile, File(description="Upload a product image to process.")],
    background_color: Annotated[str | None, Form(description="Optional replacement background color in hex format.")] = None,
) -> Response:
    original_bytes, image = await _read_and_validate_upload(file)
    background_service = get_background_service(request)
    started = time.perf_counter()
    processed_image = await background_service.remove_background_async(image)

    try:
        replacement = parse_background_color(background_color) if background_color else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if replacement is not None and processed_image.mode in {"RGBA", "LA"}:
        from PIL import Image

        background = Image.new("RGBA", processed_image.size, replacement + (255,))
        processed_image = Image.alpha_composite(background, processed_image.convert("RGBA"))
        processed_image = processed_image.convert("RGBA")

    buffer = BytesIO()
    processed_image.save(buffer, format="PNG", optimize=True)
    payload = buffer.getvalue()
    processing_ms = int((time.perf_counter() - started) * 1000)
    filename = sanitize_filename(file.filename, suffix="bg-removed")
    headers = {
        "Content-Type": "image/png",
        "Content-Disposition": f'inline; filename="{filename}.png"',
        "X-Original-Image-Size": str(len(original_bytes)),
        "X-Processed-Image-Size": str(len(payload)),
        "X-Processing-Time-Ms": str(processing_ms),
        "X-Output-Format": "png",
    }
    return Response(content=payload, media_type="image/png", headers=headers)


@api_router.post("/api/v1/images/compress", tags=["images"])
async def compress_image(
    request: Request,
    file: Annotated[UploadFile, File(description="Upload a product image to compress.")],
    output_format: Annotated[str, Form(description="The output format for the processed file.")] = "png",
    quality: Annotated[int, Form(description="Compression quality for lossy formats.")] = 85,
    max_width: Annotated[int | None, Form(description="Optional maximum output width.")] = None,
    max_height: Annotated[int | None, Form(description="Optional maximum output height.")] = None,
    background_color: Annotated[str | None, Form(description="Optional solid background for JPEG output.")] = None,
) -> Response:
    original_bytes, image = await _read_and_validate_upload(file)
    if quality < 1 or quality > 100:
        raise HTTPException(status_code=400, detail="Quality must be between 1 and 100.")
    if max_width is not None and max_width <= 0:
        raise HTTPException(status_code=400, detail="max_width must be a positive integer.")
    if max_height is not None and max_height <= 0:
        raise HTTPException(status_code=400, detail="max_height must be a positive integer.")

    normalized_format = normalize_format(output_format)
    image = resize_image_with_aspect_ratio(image, max_width=max_width, max_height=max_height)
    payload_bytes, normalized_format = _encode_image_bytes(
        image,
        output_format=normalized_format,
        quality=quality,
        background_color=background_color,
    )
    filename = sanitize_filename(file.filename, suffix=f"compressed.{normalized_format}")
    headers = {
        "Content-Type": f"image/{normalized_format}",
        "Content-Disposition": f'inline; filename="{filename}"',
        "X-Original-Image-Size": str(len(original_bytes)),
        "X-Processed-Image-Size": str(len(payload_bytes)),
        "X-Output-Format": normalized_format,
        "X-Output-Width": str(image.size[0]),
        "X-Output-Height": str(image.size[1]),
    }
    return Response(content=payload_bytes, media_type=f"image/{normalized_format}", headers=headers)


@api_router.post("/api/v1/images/process", tags=["images"])
async def process_image(
    request: Request,
    file: Annotated[UploadFile, File(description="Upload a product image for background removal and optimization.")],
    output_format: Annotated[str, Form(description="Final image format: png, jpeg, or webp.")] = "png",
    quality: Annotated[int, Form(description="Compression quality from 1 to 100.")] = 85,
    max_width: Annotated[int | None, Form(description="Optional maximum width in pixels.")] = None,
    max_height: Annotated[int | None, Form(description="Optional maximum height in pixels.")] = None,
    background_color: Annotated[str | None, Form(description="Optional replacement color for transparency when required.")] = None,
    remove_background_flag: Annotated[bool, Form(alias="remove_background", description="Whether to run background removal before optimization.")] = True,
) -> Response:
    original_bytes, image = await _read_and_validate_upload(file)
    if quality < 1 or quality > 100:
        raise HTTPException(status_code=400, detail="Quality must be between 1 and 100.")
    if max_width is not None and max_width <= 0:
        raise HTTPException(status_code=400, detail="max_width must be a positive integer.")
    if max_height is not None and max_height <= 0:
        raise HTTPException(status_code=400, detail="max_height must be a positive integer.")

    pipeline = ImagePipeline(settings, get_background_service(request))
    try:
        output_name = normalize_format(output_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await pipeline.process(
        image,
        output_format=output_name,
        quality=quality,
        max_width=max_width,
        max_height=max_height,
        background_color=background_color,
        remove_background=remove_background_flag,
        original_size_bytes=len(original_bytes),
        filename=sanitize_filename(file.filename, suffix=f"processed.{output_name}"),
    )

    payload, output_name = _encode_image_bytes(
        result.image,
        output_format=output_name,
        quality=quality,
        background_color=background_color,
    )
    headers = {
        "Content-Type": f"image/{output_name}",
        "Content-Disposition": f'inline; filename="{result.filename}"',
        "X-Original-Image-Size": str(result.original_size_bytes),
        "X-Processed-Image-Size": str(len(payload)),
        "X-Processing-Time-Ms": str(result.processing_ms),
        "X-Output-Format": output_name,
        "X-Output-Width": str(result.width),
        "X-Output-Height": str(result.height),
    }
    return Response(content=payload, media_type=f"image/{output_name}", headers=headers)
