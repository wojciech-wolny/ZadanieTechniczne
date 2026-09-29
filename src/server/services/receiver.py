"""Accept one producer and dispatch decoded samples."""

import asyncio
import logging
import socket
import time

from server.services.decoder import NonFiniteSampleError, SampleDecoder
from server.services.registry import TaskRegistry

logger = logging.getLogger(__name__)

READ_SIZE = 65536
REJECTION_LOG_INTERVAL_SECONDS = 10.0


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
        self._rejected_count = 0
        self._rejection_logged_at: float | None = None

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
        if self.producer_connected:
            self._log_rejection()
            await self._close_writer(writer)
            return
        self.producer_connected = True
        self._writers.add(writer)
        try:
            connection = writer.get_extra_info("socket")
            if connection is not None:
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            await self._read_samples(reader)
        finally:
            self._decoder.discard_remainder()
            self.producer_connected = False
            self._writers.discard(writer)
            await self._close_writer(writer)

    def _log_rejection(self) -> None:
        """Count a rejected producer and log the count at most once per interval."""
        self._rejected_count += 1
        now = time.monotonic()
        last_logged = self._rejection_logged_at
        if last_logged is not None and now - last_logged < REJECTION_LOG_INTERVAL_SECONDS:
            return
        logger.warning("rejected %s second producer connections", self._rejected_count)
        self._rejection_logged_at = now
        self._rejected_count = 0

    async def _read_samples(self, reader: asyncio.StreamReader) -> None:
        """Read chunks, decode them and dispatch finite batches.

        :param reader: socket reader
        """
        while True:
            try:
                async with asyncio.timeout(self._idle_seconds):
                    chunk = await reader.read(READ_SIZE)
            except TimeoutError:
                logger.warning("closing producer idle for %s seconds", self._idle_seconds)
                return
            except OSError:
                logger.warning("producer connection ended")
                return
            if chunk == b"":
                return
            try:
                samples = self._decoder.decode(chunk)
            except NonFiniteSampleError as error:
                self._dispatch_samples(error.samples)
                logger.warning("closing producer after a non finite sample")
                return
            self._dispatch_samples(samples)

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
