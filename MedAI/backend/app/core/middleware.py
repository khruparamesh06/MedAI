"""ASGI middleware that rejects oversized request bodies before they are buffered or spooled to disk."""
import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TOO_LARGE = json.dumps({"detail": "Request body is too large."}).encode()


class BodySizeLimitMiddleware:
    """
    Starlette spools multipart *file* parts to disk without a size limit, so the upload route's own
    check runs only after the whole body has been received. This middleware enforces a hard cap
    while the body streams in: by Content-Length when present, otherwise by counting bytes.
    """

    def __init__(self, app: ASGIApp, default_limit: int, upload_limit: int, upload_paths: tuple[str, ...]):
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit
        self.upload_paths = upload_paths

    def _limit_for(self, scope: Scope) -> int:
        return self.upload_limit if scope["path"] in self.upload_paths else self.default_limit

    @staticmethod
    async def _reject(send: Send) -> None:
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(_TOO_LARGE)).encode())]})
        await send({"type": "http.response.body", "body": _TOO_LARGE})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = self._limit_for(scope)
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    if int(value) > limit:
                        await self._reject(send)
                        return
                except ValueError:
                    pass

        received = 0
        exceeded = False
        replaced = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal replaced
            if exceeded:
                # Whatever the app tried to answer (usually a parse error), the real cause is the size.
                if message["type"] == "http.response.start" and not replaced:
                    replaced = True
                    await self._reject(send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if exceeded and not replaced:
                await self._reject(send)
                return
            raise
