"""Environment configuration for the processing server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from common.protocol import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_TCP_HOST,
    DEFAULT_TCP_PORT,
)

MAX_TASKS = 32
MAX_TASKS_LIMIT = 256
PRODUCER_IDLE_SECONDS = 30.0
MAX_PRODUCER_IDLE_SECONDS = 3600.0


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables.

    :attr tcp_host: bind address of the sample receiver
    :attr tcp_port: bind port of the sample receiver
    :attr http_host: bind address of the HTTP server
    :attr http_port: bind port of the HTTP server
    :attr max_tasks: maximum number of tasks kept at once
    :attr producer_idle_seconds: seconds without data before a producer is disconnected
    :attr docs_enabled: whether the interactive docs and the OpenAPI schema are served
    """

    model_config = SettingsConfigDict(extra="ignore")

    tcp_host: str = Field(default=DEFAULT_TCP_HOST, min_length=1)
    tcp_port: int = Field(default=DEFAULT_TCP_PORT, ge=0, le=65535)
    http_host: str = Field(default=DEFAULT_HTTP_HOST, min_length=1)
    http_port: int = Field(default=DEFAULT_HTTP_PORT, ge=0, le=65535)
    max_tasks: int = Field(default=MAX_TASKS, ge=1, le=MAX_TASKS_LIMIT)
    producer_idle_seconds: float = Field(
        default=PRODUCER_IDLE_SECONDS,
        gt=0,
        le=MAX_PRODUCER_IDLE_SECONDS,
        allow_inf_nan=False,
    )
    docs_enabled: bool = True
