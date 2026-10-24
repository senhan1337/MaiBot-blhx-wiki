"""HTTP utilities for wiki requests.

Network and HTTP failures are converted to empty return values instead of
being raised.
"""
from __future__ import annotations

import random
from collections.abc import Callable
from typing import Final

import httpx


USER_AGENTS: Final[tuple[str, ...]] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
)

COOKIE: Final[str] = ""
REFERER: Final[str] = "https://wiki.biligame.com/"
TIMEOUT: Final[float] = 20.0

GET_HEADERS: Final[dict[str, str]] = {
    "cookie": COOKIE,
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
}

BYTE_HEADERS: Final[dict[str, str]] = {
    "cookie": COOKIE,
    "Content-Type": "application/json; charset=utf-8",
}

POST_HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
}


def _random_user_agent() -> str:
    """Return one of the seven user agents used by the original plugin."""
    return random.choice(USER_AGENTS)


def _apply_interceptor(request: httpx.Request) -> None:
    """Emulate OkHttp's interceptor by replacing UA and setting Referer."""
    request.headers["User-Agent"] = _random_user_agent()
    request.headers["Referer"] = REFERER


def _raise_for_status(response: httpx.Response) -> None:
    """Treat non-2xx/3xx HTTP responses as failures for empty-value parity."""
    response.raise_for_status()


async def _apply_interceptor_async(request: httpx.Request) -> None:
    """Async counterpart of the OkHttp-style request interceptor."""
    _apply_interceptor(request)


class HttpClient:
    """Small httpx client for wiki requests.

    ``get`` is asynchronous because the source method is a suspend function.
    ``post`` and ``get_byte_array`` are synchronous, matching their source
    signatures. All request failures, including HTTP status errors, are caught.
    """

    def __init__(
        self,
        timeout: float = TIMEOUT,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        """Create a client with a 20-second default connection/request timeout."""
        self._timeout = timeout
        self._logger = logger
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            event_hooks={"request": [_apply_interceptor]},
        )
        self._async_client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            event_hooks={"request": [_apply_interceptor_async]},
        )

    def _debug(self, message: str) -> None:
        """Optionally report a compact debug message without printing a traceback."""
        if self._logger is not None:
            try:
                self._logger(message)
            except Exception:
                pass

    async def get(self, url: str, timeout: float | None = None) -> str:
        """GET ``url`` and return its decoded response body, or ``""`` on failure.

        ``timeout`` overrides the client default for this request when provided.
        """
        try:
            options = {} if timeout is None else {"timeout": timeout}
            response = await self._async_client.get(url, headers=GET_HEADERS, **options)
            _raise_for_status(response)
            return response.text
        except Exception as exc:
            self._debug(f"HTTP GET failed: {exc}")
            return ""

    def post(self, url: str, post_body: str) -> str:
        """POST form-encoded ``post_body`` and return body text, or ``""`` on failure."""
        try:
            response = self._client.post(url, content=post_body, headers=POST_HEADERS)
            _raise_for_status(response)
            return response.text
        except Exception as exc:
            self._debug(f"HTTP POST failed: {exc}")
            return ""

    async def get_bytes(self, url: str, timeout: float | None = None) -> bytes | None:
        """GET binary data as-is (no legacy trailing byte), or ``None`` on failure."""
        try:
            options = {} if timeout is None else {"timeout": timeout}
            response = await self._async_client.get(url, headers=BYTE_HEADERS, **options)
            _raise_for_status(response)
            return response.content
        except Exception as exc:
            self._debug(f"HTTP byte GET failed: {exc}")
            return None

    def get_byte_array(self, url: str) -> bytes | None:
        """GET binary data and append one compatibility byte.

        The legacy stream gets one random byte in the inclusive range 1..100
        after the response, so the result length is always the original body
        length plus one on success.
        """
        try:
            response = self._client.get(url, headers=BYTE_HEADERS)
            _raise_for_status(response)
            body = response.content
            # Compatibility: the stream gets one extra
            # random byte after all response bytes have been consumed.
            return body + bytes((random.randint(1, 100),))
        except Exception as exc:
            self._debug(f"HTTP byte GET failed: {exc}")
            return None

    async def aclose(self) -> None:
        """Close both underlying httpx clients."""
        try:
            await self._async_client.aclose()
        except Exception as exc:
            self._debug(f"Async HTTP client close failed: {exc}")
        try:
            self._client.close()
        except Exception as exc:
            self._debug(f"HTTP client close failed: {exc}")

    def close(self) -> None:
        """Close the synchronous client.

        The asynchronous client should preferably be closed with ``aclose``
        from an async plugin lifecycle method.
        """
        try:
            self._client.close()
        except Exception as exc:
            self._debug(f"HTTP client close failed: {exc}")


http_client = HttpClient()


async def get(url: str, timeout: float | None = None) -> str:
    """Module-level async GET wrapper; returns ``""`` on any failure."""
    return await http_client.get(url, timeout=timeout)


def post(url: str, post_body: str) -> str:
    """Module-level form POST wrapper; returns ``""`` on any failure."""
    return http_client.post(url, post_body)


async def get_bytes(url: str, timeout: float | None = None) -> bytes | None:
    """Module-level binary GET wrapper; returns ``None`` on any failure."""
    return await http_client.get_bytes(url, timeout=timeout)


def get_byte_array(url: str) -> bytes | None:
    """Module-level binary GET wrapper; returns ``None`` on any failure."""
    return http_client.get_byte_array(url)
