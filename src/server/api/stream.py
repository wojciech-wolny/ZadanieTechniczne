"""Sample stream status route."""

from fastapi import APIRouter, status

from server.dependencies import SampleReceiverDep
from server.schemas import StreamRead

router = APIRouter(tags=["stream"])


@router.get("/stream", status_code=status.HTTP_200_OK)
async def read_stream(receiver: SampleReceiverDep) -> StreamRead:
    """Return whether a producer is connected and how many samples arrived.

    :param receiver: shared sample receiver
    :return: stream status
    """
    return StreamRead(
        producer_connected=receiver.producer_connected,
        samples_received=receiver.samples_received,
    )
