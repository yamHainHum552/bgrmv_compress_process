from __future__ import annotations

import time
from dataclasses import dataclass

from PIL import Image

from app.core.config import Settings
from app.services.background_removal import BackgroundRemovalService
from app.services.compression import resize_image_with_aspect_ratio
from app.utils.validation import encode_image, normalize_background_color, parse_background_color


@dataclass(slots=True)
class ImageProcessingResult:
    image: Image.Image
    output_format: str
    filename: str
    size_bytes: int
    original_size_bytes: int
    processing_ms: int
    width: int
    height: int


class ImagePipeline:
    def __init__(self, settings: Settings, background_service: BackgroundRemovalService) -> None:
        self.settings = settings
        self.background_service = background_service

    async def process(
        self,
        image: Image.Image,
        *,
        output_format: str,
        quality: int,
        max_width: int | None,
        max_height: int | None,
        background_color: str | None,
        remove_background: bool,
        original_size_bytes: int,
        filename: str,
    ) -> ImageProcessingResult:
        started = time.perf_counter()
        working_image = image.copy()

        if remove_background:
            working_image = await self.background_service.remove_background_async(working_image)

        if working_image.mode not in {"RGBA", "LA", "RGB", "L", "P"}:
            working_image = working_image.convert("RGBA")

        working_image = resize_image_with_aspect_ratio(
            working_image,
            max_width=max_width,
            max_height=max_height,
        )

        output_format_name = output_format.lower()
        background_rgb = parse_background_color(background_color) if background_color else None
        encoded = encode_image(
            working_image,
            output_format=output_format_name,
            quality=quality,
            background_color=background_rgb,
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        final_width, final_height = working_image.size

        return ImageProcessingResult(
            image=working_image,
            output_format=output_format_name,
            filename=filename,
            size_bytes=len(encoded),
            original_size_bytes=original_size_bytes,
            processing_ms=elapsed_ms,
            width=final_width,
            height=final_height,
        )
