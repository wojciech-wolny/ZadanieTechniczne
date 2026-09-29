"""Request and response models for the processing server."""

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from server.services.tasks import ProcessingTask

MAX_WINDOW_SIZE = 100000

type SinkName = Literal["null", "stdout"]


class PassthroughConfig(BaseModel):
    """Configuration of the passthrough algorithm."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["passthrough"]


class AverageConfig(BaseModel):
    """Configuration of the window average algorithm.

    :attr window_size: number of samples in one window
    """

    model_config = ConfigDict(extra="forbid")

    name: Literal["average"]
    window_size: int = Field(ge=1, le=MAX_WINDOW_SIZE, strict=True)


class LinearRegressionConfig(BaseModel):
    """Configuration of the windowed linear regression algorithm.

    :attr window_size: number of samples in one window
    """

    model_config = ConfigDict(extra="forbid")

    name: Literal["linear_regression"]
    window_size: int = Field(ge=2, le=MAX_WINDOW_SIZE, strict=True)


AlgorithmConfig = Annotated[
    PassthroughConfig | AverageConfig | LinearRegressionConfig,
    Field(discriminator="name"),
]


class TaskCreate(BaseModel):
    """Request body used to create a processing task.

    :attr algorithm: algorithm name and its parameters
    :attr sink: where numeric results are written
    """

    model_config = ConfigDict(extra="forbid")

    algorithm: AlgorithmConfig
    sink: SinkName = "null"


class TaskRead(BaseModel):
    """Public view of a processing task.

    :attr task_id: lowercase UUID4 text
    :attr algorithm: algorithm name and parameters
    :attr sink: sink name
    :attr status: running or failed
    :attr created_at: creation time in UTC
    :attr statistics: samples processed and algorithm statistics
    :attr error: exception class name when the task failed
    """

    task_id: str
    algorithm: AlgorithmConfig
    sink: SinkName
    status: Literal["running", "failed"]
    created_at: datetime
    statistics: dict[str, float | int | None]
    error: str | None

    @classmethod
    def from_task(cls, task: "ProcessingTask") -> Self:
        """Build a response model from a processing task.

        :param task: stored task
        :return: serializable task view
        """
        return cls(
            task_id=task.task_id,
            algorithm=task.algorithm_config,
            sink=task.sink_name,
            status=task.status,
            created_at=task.created_at,
            statistics=task.read_statistics(),
            error=task.error,
        )


class StreamRead(BaseModel):
    """Connection status of the sample receiver.

    :attr producer_connected: whether a producer is connected
    :attr samples_received: finite samples dispatched since startup
    """

    producer_connected: bool
    samples_received: int
