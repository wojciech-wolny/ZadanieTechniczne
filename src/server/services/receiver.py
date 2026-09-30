"""Accept one producer and dispatch decoded samples."""

import asyncio
import logging

from server.services.decoder import NonFiniteSampleError, SampleDecoder
from server.services.registry import TaskRegistry

logger = logging.getLogger(__name__)

READ_SIZE = 65536


class SampleReceiver:
    """Accept one producer and dispatch decoded samples.

    :attr producer_connected: whether a producer socket is active
    :attr samples_received: finite samples dispatched since startup
    :attr port: requested TCP port, replaced by the bound port after start
    """

    def __init__(
        self,
        registry: TaskRegistry,
        host: str,
        port: int,
        idle_seconds: float,
    ) -> None:
        self._registry = registry
        self._host = host
        self._idle_seconds = idle_seconds
        self.producer_connected = False
        self.samples_received = 0
        self.port = port
        self._server: asyncio.Server | None = None
        self._decoder = SampleDecoder()
        self._writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        """Start listening for a producer connection."""
        self._server = await asyncio.start_server(
            self._serve_producer,
            self._host,
            self.port,
        )
        sockets = self._server.sockets
        if sockets:
            self.port = sockets[0].getsockname()[1]
        logger.info("sample receiver listening on %s:%s", self._host, self.port)

    async def stop(self) -> None:
        """Stop listening and close active producer connections."""
        writers = list(self._writers)
        for writer in writers:
            if not writer.is_closing():
                writer.close()
        for writer in writers:
            try:
                await writer.wait_closed()
            except OSError:
                continue
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _serve_producer(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Read one producer connection until it ends or fails.

        :param reader: socket reader
        :param writer: socket writer
        """
        if not await self._take_producer_slot(writer):
            return
        try:
            await self._read_samples(reader)
        finally:
            await self._release_producer_slot(writer)

    async def _take_producer_slot(self, writer: asyncio.StreamWriter) -> bool:
        """Reserve the single producer slot or reject this connection.

        :param writer: socket writer
        :return: whether this connection was accepted
        """
        if self.producer_connected:
            logger.warning("rejected a second producer connection")
            await self._close_writer(writer)
            return False
        self.producer_connected = True
        self._writers.add(writer)
        return True

    async def _release_producer_slot(self, writer: asyncio.StreamWriter) -> None:
        """Release the producer slot and close the connection.

        :param writer: socket writer
        """
        self._decoder.discard_remainder()
        self.producer_connected = False
        self._writers.discard(writer)
        await self._close_writer(writer)

    async def _read_samples(self, reader: asyncio.StreamReader) -> None:
        """Read chunks, decode them and dispatch finite batches.

        :param reader: socket reader
        """
        while True:
            chunk = await self._read_chunk(reader)
            if chunk is None:
                return
            if not self._decode_and_dispatch(chunk):
                return

    async def _read_chunk(self, reader: asyncio.StreamReader) -> bytes | None:
        """Read one chunk or return None when the connection should close.

        :param reader: socket reader
        :return: read bytes, or None on timeout, socket error or disconnect
        """
        try:
            async with asyncio.timeout(self._idle_seconds):
                chunk = await reader.read(READ_SIZE)
        except TimeoutError:
            logger.warning("closing producer idle for %s seconds", self._idle_seconds)
            return None
        except OSError:
            logger.warning("producer connection ended")
            return None
        if chunk == b"":
            return None
        return chunk

    def _decode_and_dispatch(self, chunk: bytes) -> bool:
        """Decode one chunk and dispatch its finite prefix.

        :param chunk: bytes from one TCP read
        :return: whether the connection should stay open
        """
        try:
            samples = self._decoder.decode(chunk)
        except NonFiniteSampleError as error:
            self._dispatch_samples(error.samples)
            logger.warning("closing producer after a non finite sample")
            return False
        self._dispatch_samples(samples)
        return True

    def _dispatch_samples(self, samples: list[float]) -> None:
        """Deliver decoded samples to the tasks and count them.

        :param samples: finite samples from one read
        """
        if not samples:
            return
        self._registry.dispatch(samples)
        self.samples_received += len(samples)

    async def _close_writer(self, writer: asyncio.StreamWriter) -> None:
        """Close a socket writer and ignore a peer that is already gone.

        :param writer: socket writer
        """
        if not writer.is_closing():
            writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            return
