from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from rembg import remove
from rembg.session_factory import new_session

from app.core.config import Settings


class BackgroundRemovalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.model_name
        self.session = None
        self.executor = ThreadPoolExecutor(max_workers=settings.thread_pool_size)
        self.inference_semaphore = asyncio.Semaphore(settings.inference_concurrency)

    def initialize(self) -> None:
        if self.session is None:
            self.session = new_session(self.model_name)

    @property
    def ready(self) -> bool:
        return self.session is not None

    async def remove_background_async(self, image: Image.Image) -> Image.Image:
        self.initialize()
        async with self.inference_semaphore:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.executor, self._remove_background_sync, image)

    def _remove_background_sync(self, image: Image.Image) -> Image.Image:
        result = remove(image.copy(), session=self.session)
        if result.mode != "RGBA":
            result = result.convert("RGBA")
        return result
