"""Task collection routes."""

from fastapi import APIRouter, HTTPException, status

from server.dependencies import TaskRegistryDep
from server.schemas import TaskCreate, TaskRead

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


@router.get("", status_code=status.HTTP_200_OK)
async def list_tasks(registry: TaskRegistryDep) -> list[TaskRead]:
    """List tasks in creation order.

    :param registry: shared task registry
    :return: running and failed tasks
    """
    reads: list[TaskRead] = []
    for task in registry.list_tasks():
        reads.append(TaskRead.from_task(task))
    return reads


@router.get("/{task_id}", status_code=status.HTTP_200_OK)
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


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, registry: TaskRegistryDep) -> None:
    """Stop and remove a task.

    :param task_id: task identifier
    :param registry: shared task registry
    :raises HTTPException: when the task does not exist
    """
    removed = registry.remove_task(task_id)
    if removed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
