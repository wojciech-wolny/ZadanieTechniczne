"""Create, list and dispatch processing tasks."""

import logging

from server.schemas import TaskCreate
from server.services.tasks import ProcessingTask
from server.settings import MAX_TASKS

logger = logging.getLogger(__name__)


class TaskLimitError(Exception):
    """Raised when a new task would exceed the configured maximum."""


class TaskRegistry:
    """Keep tasks in creation order and deliver samples to running ones.

    :attr max_tasks: maximum number of stored tasks
    """

    def __init__(self, max_tasks: int = MAX_TASKS) -> None:
        self.max_tasks = max_tasks
        self._tasks: dict[str, ProcessingTask] = {}

    def create_task(self, config: TaskCreate) -> ProcessingTask:
        """Create a task when the registry is below its limit.

        :param config: task configuration
        :return: created task
        :raises TaskLimitError: when the task limit is reached
        """
        if len(self._tasks) >= self.max_tasks:
            raise TaskLimitError("Task limit reached")
        task = ProcessingTask.create(config)
        self._tasks[task.task_id] = task
        return task

    def find_task(self, task_id: str) -> ProcessingTask | None:
        """Return one task by id.

        :param task_id: task identifier
        :return: task or None when it is absent
        """
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[ProcessingTask]:
        """Return all tasks in creation order, including failed ones.

        :return: tasks from oldest to newest
        """
        return list(self._tasks.values())

    def remove_task(self, task_id: str) -> ProcessingTask | None:
        """Stop a task and drop it from the registry.

        :param task_id: identifier returned at creation
        :return: removed task, or None when the id is unknown
        """
        task = self._tasks.pop(task_id, None)
        if task is None:
            return None
        task.close_sink()
        return task

    def close_all(self) -> None:
        """Close the sink of every stored task and keep going when one close fails."""
        for task in self._tasks.values():
            try:
                task.close_sink()
            except Exception:
                logger.warning("sink close failed for task %s", task.task_id)

    def dispatch(self, samples: list[float]) -> None:
        """Deliver samples to every running task captured at the start.

        :param samples: finite samples from one decoded read
        """
        running: list[ProcessingTask] = []
        for task in self._tasks.values():
            if task.status == "running":
                running.append(task)
        for task in running:
            try:
                task.process_samples(samples)
            except Exception as error:
                task.record_failure(type(error).__name__)
                try:
                    task.close_sink()
                except Exception:
                    logger.warning("sink close failed for task %s", task.task_id)
