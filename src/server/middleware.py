"""ASGI middleware that bounds the HTTP request body."""

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BYTES = 16384
MAX_LENGTH_DIGITS = len(str(MAX_REQUEST_BYTES))


def read_content_length(scope: Scope) -> int:
    """Return the declared request body length.

    :param scope: ASGI connection scope
    :return: Content Length value, one above the limit when it has too many digits,
        or 0 when the header is missing or not a number
    """
    for name, value in scope["headers"]:
        if name != b"content-length" or not value.isdigit():
            continue
        digits = value.lstrip(b"0")
        if len(digits) > MAX_LENGTH_DIGITS:
            return MAX_REQUEST_BYTES + 1
        return int(digits or b"0")
    return 0


class RequestSizeLimitMiddleware:
    """Reject HTTP requests whose body is larger than the allowed size.

    :attr app: wrapped ASGI application
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Read a bounded body, then pass the request on or answer 413.

        :param scope: ASGI connection scope
        :param receive: ASGI receive channel
        :param send: ASGI send channel
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if read_content_length(scope) > MAX_REQUEST_BYTES:
            await self._reject(scope, receive, send)
            return
        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_REQUEST_BYTES:
                await self._reject(scope, receive, send)
                return
            more_body = message.get("more_body", False)

        body_delivered = False

        async def replay_body() -> Message:
            """Return the buffered body once, then the original channel.

            :return: next ASGI message
            """
            nonlocal body_delivered
            if body_delivered:
                return await receive()
            body_delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_body, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer that the request body is too large.

        :param scope: ASGI connection scope
        :param receive: ASGI receive channel
        :param send: ASGI send channel
        """
        response = JSONResponse(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            content={"detail": "Request body too large"},
        )
        await response(scope, receive, send)
