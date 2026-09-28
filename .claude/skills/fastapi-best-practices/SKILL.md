---
name: fastapi-best-practices
description: Applies FastAPI and Pydantic v2 best practices for REST API design, application structure, lifespan, dependencies, models and error handling. Use when creating or changing FastAPI endpoints, routers, request or response models, or the server startup of this project.
---

# FastAPI Best Practices

Always follow the `python-code-style` skill as well.

Target **Python 3.14.7** with current FastAPI and Pydantic 2.12 or newer (first release supporting 3.14). Keep `Annotated[...]` for dependencies and discriminated unions because FastAPI and Pydantic read it at runtime.

## Structure

```
src/server/
    main.py          create_app, lifespan
    api/tasks.py     APIRouter with task endpoints
    schemas.py       Pydantic request and response models
    dependencies.py  Depends providers
    services/        business logic, no FastAPI imports
```

Keep endpoints thin: validate input, call a service, return a model. Business logic never imports FastAPI.

## Rules

1. **Create the app in a function** `create_app()` so tests build a fresh instance.
2. **Use `lifespan`**, never `@app.on_event`. Start and stop background resources (TCP server, task registry) there and keep them on `app.state`.
3. **Use `APIRouter`** with `prefix` and `tags`, one router per resource.
4. **Use `Annotated` dependencies:** `TaskRegistryDep = Annotated[TaskRegistry, Depends(get_task_registry)]`.
5. **Pydantic v2 models** for every request and response. Set `response_model` or a return annotation, and `status_code` explicitly.
6. **Separate models:** `TaskCreate` for input, `TaskRead` for output. Never return internal objects directly.
7. **Discriminated unions** for variant input, for example algorithm parameters: `Field(discriminator="algorithm")`.
8. **Validate with `Field`** constraints (`gt=0`, `ge=1`) instead of manual checks.
9. **Use `fastapi.status` constants**: `201` on create, `204` on delete, `404` when missing, `422` left to validation.
10. **Raise `HTTPException`** from endpoints only. Services return `None` or raise domain exceptions mapped by an exception handler.
11. **Use `async def`** only when the body awaits or is non blocking. Never call blocking I/O inside `async def`.
12. **Settings** through `pydantic_settings.BaseSettings` read from environment.
13. Use nouns and plural resource paths: `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`, `DELETE /tasks/{task_id}`.

## Example

```python
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status


@asynccontextmanager
async def run_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the sample receiver and task registry for the application lifetime.

    :param app: application instance
    """
    app.state.task_registry = TaskRegistry()
    receiver = await start_sample_receiver(app.state.task_registry)
    yield
    await receiver.stop()


def get_task_registry(request: Request) -> TaskRegistry:
    """Return the task registry stored on the application state.

    :param request: current request
    :return: shared task registry
    """
    return request.app.state.task_registry


TaskRegistryDep = Annotated[TaskRegistry, Depends(get_task_registry)]

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(task_create: TaskCreate, registry: TaskRegistryDep) -> TaskRead:
    """Create and start a processing task.

    :param task_create: task configuration
    :param registry: shared task registry
    :return: created task
    """
    task = registry.create_task(task_create)
    return TaskRead.from_task(task)


@router.get("/{task_id}")
async def read_task(task_id: str, registry: TaskRegistryDep) -> TaskRead:
    """Return configuration and statistics of one task.

    :param task_id: task identifier
    :param registry: shared task registry
    :return: task information
    :raises HTTPException: when the task does not exist
    """
    task = registry.find_task(task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.from_task(task)


def create_app() -> FastAPI:
    """Build the FastAPI application.

    :return: configured application
    """
    app = FastAPI(title="Processing Server", lifespan=run_lifespan)
    app.include_router(router)
    return app
```

## Models example

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PassthroughConfig(BaseModel):
    """Configuration of the passthrough algorithm."""

    algorithm: Literal["passthrough"]


class AverageConfig(BaseModel):
    """Configuration of the window average algorithm.

    :attr window_size: number of samples in one window
    """

    algorithm: Literal["average"]
    window_size: int = Field(gt=0)


AlgorithmConfig = Annotated[PassthroughConfig | AverageConfig, Field(discriminator="algorithm")]


class TaskCreate(BaseModel):
    """Request body used to create a processing task."""

    config: AlgorithmConfig
    sink: Literal["null", "stdout"] = "null"
```
