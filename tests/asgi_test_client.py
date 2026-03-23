from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import httpx


class SyncASGITestClient:
    """Minimal sync wrapper around httpx.ASGITransport for unittest-style tests."""

    def __init__(self, app: Any, *, base_url: str = "http://testserver", ticker_interval: float = 0.01) -> None:
        self._app = app
        self._base_url = base_url
        self._ticker_interval = ticker_interval

    async def _ticker(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await asyncio.sleep(self._ticker_interval)

    async def _request_async(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(app=self._app)
        stop_event = asyncio.Event()
        ticker = asyncio.create_task(self._ticker(stop_event))
        try:
            async with httpx.AsyncClient(transport=transport, base_url=self._base_url) as client:
                return await client.request(method, url, **kwargs)
        finally:
            stop_event.set()
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request_async(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        """Match TestClient's close() surface for tearDown cleanup."""
        return None

    def __enter__(self) -> "SyncASGITestClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
