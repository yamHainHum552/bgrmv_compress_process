from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceInfoResponse(BaseModel):
    name: str = Field(..., description="Application name")
    version: str = Field("1.0.0", description="API version")
    status: str = Field("ok", description="API status")


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Health status")


class ReadyResponse(BaseModel):
    status: str = Field("ready", description="Readiness status")
    ready: bool = Field(..., description="Whether the model is initialized")
    model_name: str = Field(..., description="Configured rembg model")


class InfoResponse(BaseModel):
    supported_input_formats: list[str] = Field(..., description="Accepted input image formats")
    supported_output_formats: list[str] = Field(..., description="Accepted output image formats")
    max_upload_size_mb: int = Field(..., description="Maximum upload size in MB")
    max_image_pixels: int = Field(..., description="Maximum supported pixel count")
    max_image_dimension: int = Field(..., description="Maximum image width/height in pixels")
    default_output_format: str = Field(..., description="Default output format")
    default_image_quality: int = Field(..., description="Default compression quality")
    inference_concurrency: int = Field(..., description="Maximum simultaneous AI inference requests")
    thread_pool_size: int = Field(..., description="Thread pool size for CPU-bound work")
