"""Dependencies shared by the HTTP routes."""

from typing import Annotated

from fastapi import Depends, Request

from server.services.receiver import SampleReceiver
from server.services.registry import TaskRegistry


def get_task_registry(request: Request) -> TaskRegistry:
    """Return the task registry stored on the application state.

    :param request: current request
    :return: shared task registry
    """
    return request.app.state.task_registry


def get_sample_receiver(request: Request) -> SampleReceiver:
    """Return the sample receiver stored on the application state.

    :param request: current request
    :return: shared sample receiver
    """
    return request.app.state.sample_receiver


TaskRegistryDep = Annotated[TaskRegistry, Depends(get_task_registry)]
SampleReceiverDep = Annotated[SampleReceiver, Depends(get_sample_receiver)]
