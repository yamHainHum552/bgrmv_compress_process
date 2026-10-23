from __future__ import annotations

from PIL import Image


def resize_image_with_aspect_ratio(
    image: Image.Image,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
) -> Image.Image:
    width, height = image.size
    if max_width is None and max_height is None:
        return image

    if max_width is not None and width > max_width:
        scale = max_width / width
        width = max_width
        height = max(1, int(height * scale))

    if max_height is not None and height > max_height:
        scale = max_height / height
        height = max_height
        width = max(1, int(width * scale))

    if width == image.size[0] and height == image.size[1]:
        return image

    return image.resize((width, height), Image.Resampling.LANCZOS)


def qualifies_for_transparency(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA", "P"}
