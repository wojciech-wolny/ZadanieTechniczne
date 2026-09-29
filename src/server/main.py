"""Processing server application and console entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from server.api.stream import router as stream_router
from server.api.tasks import router as tasks_router
from server.middleware import RequestSizeLimitMiddleware
from server.services.receiver import SampleReceiver
from server.services.registry import TaskLimitError, TaskRegistry
from server.settings import Settings

API_V1_PREFIX = "/api/v1"
HTTP_CONCURRENCY_LIMIT = 64
DOCS_URL = "/docs"
REDOC_URL = "/redoc"
OPENAPI_URL = "/openapi.json"


@asynccontextmanager
async def run_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the sample receiver and task registry for the application lifetime.

    :param app: application instance
    """
    settings: Settings = app.state.settings
    registry = TaskRegistry(max_tasks=settings.max_tasks)
    receiver = SampleReceiver(
        registry,
        settings.tcp_host,
        settings.tcp_port,
        settings.producer_idle_seconds,
    )
    app.state.task_registry = registry
    app.state.sample_receiver = receiver
    await receiver.start()
    try:
        yield
    finally:
        await receiver.stop()


def handle_task_limit(_request: Request, _error: TaskLimitError) -> JSONResponse:
    """Return conflict when the task limit is reached.

    :param _request: current request
    :param _error: limit error from the registry
    :return: error response
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Task limit reached"},
    )


def create_app() -> FastAPI:
    """Build the FastAPI application from the environment settings.

    :return: configured application
    """
    settings = Settings()
    app = FastAPI(
        title="Processing Server",
        lifespan=run_lifespan,
        docs_url=DOCS_URL if settings.docs_enabled else None,
        redoc_url=REDOC_URL if settings.docs_enabled else None,
        openapi_url=OPENAPI_URL if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_exception_handler(TaskLimitError, handle_task_limit)
    api_v1 = APIRouter(prefix=API_V1_PREFIX)
    api_v1.include_router(tasks_router)
    api_v1.include_router(stream_router)
    app.include_router(api_v1)
    return app


def main() -> None:
    """Run the HTTP server and the sample receiver."""
    app = create_app()
    settings: Settings = app.state.settings
    uvicorn.run(
        app,
        host=settings.http_host,
        port=settings.http_port,
        limit_concurrency=HTTP_CONCURRENCY_LIMIT,
        server_header=False,
    )


if __name__ == "__main__":
    main()
