from __future__ import annotations

import io
import re
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_INPUT_FORMATS = {"PNG", "JPEG", "WEBP"}
SUPPORTED_OUTPUT_FORMATS = {"PNG", "JPEG", "WEBP"}


def normalize_format(value: str | None, *, default: str = "png") -> str:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"jpg", "jpeg"}:
        return "jpeg"
    if normalized in {"png", "webp"}:
        return normalized
    raise ValueError(f"Unsupported output format: {value!r}. Supported formats are PNG, JPEG, and WEBP.")


def sanitize_filename(name: str | None, suffix: str = "processed") -> str:
    raw_name = (name or "image").strip() or "image"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip(".-") or "image"
    return f"{sanitized}-{suffix}"


def parse_background_color(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    color = value.strip()
    if not color:
        return None
    if not re.fullmatch(r"#?[0-9A-Fa-f]{6}", color):
        raise ValueError("Background color must be a valid hex color such as '#FFFFFF'.")
    hex_value = color if color.startswith("#") else f"#{color}"
    return tuple(int(hex_value[i : i + 2], 16) for i in (1, 3, 5))


def validate_upload_size(size: int, max_size_bytes: int) -> None:
    if size <= 0:
        raise ValueError("Uploaded file is empty.")
    if size > max_size_bytes:
        raise ValueError(
            f"Uploaded file exceeds the maximum allowed size of {max_size_bytes / (1024 * 1024):.0f} MB."
        )


def validate_image_dimensions(width: int, height: int, max_pixels: int, max_dimension: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions are invalid.")
    if max(width, height) > max_dimension:
        raise ValueError(
            f"Image dimension exceeds the maximum supported size of {max_dimension} pixels on either side."
        )
    if width * height > max_pixels:
        raise ValueError(
            f"Image pixel count exceeds the maximum supported value of {max_pixels} pixels."
        )


def decode_image(data: bytes, *, max_pixels: int, max_dimension: int) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded file is not a valid image or is corrupted.") from exc

    try:
        image_format = (image.format or "UNKNOWN").upper()
        if image_format not in SUPPORTED_INPUT_FORMATS:
            raise ValueError(
                f"Unsupported image format: {image_format}. Supported formats are {', '.join(sorted(SUPPORTED_INPUT_FORMATS))}."
            )
        image = ImageOps.exif_transpose(image)
        image.load()
        width, height = image.size
        validate_image_dimensions(width, height, max_pixels=max_pixels, max_dimension=max_dimension)
        return image.copy()
    except Exception:
        image.close()
        raise


def encode_image(
    image: Image.Image,
    *,
    output_format: str,
    quality: int,
    background_color: tuple[int, int, int] | None = None,
) -> bytes:
    output_format = normalize_format(output_format, default="png")
    if output_format == "jpeg":
        if image.mode in {"RGBA", "LA", "P"}:
            if background_color is None:
                background_color = (255, 255, 255)
            background = Image.new("RGBA", image.size, background_color + (255,))
            composited = Image.alpha_composite(background, image.convert("RGBA"))
            rgb_image = composited.convert("RGB")
        else:
            rgb_image = image.convert("RGB")
        with io.BytesIO() as buffer:
            rgb_image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            return buffer.getvalue()

    if output_format == "webp":
        with io.BytesIO() as buffer:
            if image.mode in {"RGBA", "LA"}:
                image.save(buffer, format="WEBP", quality=quality, method=6, lossless=False)
            else:
                image.save(buffer, format="WEBP", quality=quality, method=6, lossless=False)
            return buffer.getvalue()

    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()


def normalize_background_color(value: str | None, default: str = "#FFFFFF") -> tuple[int, int, int] | None:
    color = value or default
    return parse_background_color(color)
