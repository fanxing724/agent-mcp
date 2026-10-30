"""Bounded HTTP requests; mutations are never retried automatically."""

import asyncio
import json
import re
from typing import Any

import httpx

from .config import Settings


class MediaError(Exception):
    def __init__(
        self, code: str, message: str, *, retryable: bool = False, request_id: str | None = None
    ):
        self.details = {
            "code": code,
            "message": message,
            "retryable": retryable,
            "request_id": request_id,
        }
        super().__init__(json.dumps(self.details, ensure_ascii=False))


class MediaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._slots = asyncio.Semaphore(settings.concurrency)
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.read_timeout, connect=settings.connect_timeout),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def close(self):
        await self._http.aclose()

    def clean(self, message: str) -> str:
        if self.settings.api_key:
            message = message.replace(self.settings.api_key, "[REDACTED]")
        return re.sub(r"sk-as-[A-Za-z0-9_-]+", "[REDACTED]", message)[:500]

    async def request(
        self, method: str, path: str, body: dict | None = None, *, asynchronous: bool = False
    ) -> dict[str, Any]:
        if not self.settings.api_key:
            raise MediaError("configuration_missing", "Set AGENTSCOPE_API_KEY at deployment time")
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        if asynchronous:
            headers["X-DashScope-Async"] = "enable"
        try:
            async with self._slots:
                response = await self._http.request(
                    method,
                    self.settings.base_url.rstrip("/") + path,
                    json=body,
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            code = "submission_unknown" if method == "POST" else "network_error"
            raise MediaError(
                code,
                "Request interrupted. Submission may have been accepted; do not blindly resubmit."
                if method == "POST"
                else "Task query interrupted; try querying again.",
                retryable=method == "GET",
            ) from None
        request_id = response.headers.get("X-Proxy-Request-Id")
        try:
            data = response.json()
        except ValueError:
            raise MediaError(
                "invalid_response", "Expected a JSON response from media API", request_id=request_id
            ) from None
        if not isinstance(data, dict):
            raise MediaError(
                "invalid_response", "Expected an object response", request_id=request_id
            )
        if response.is_error or response.is_redirect or data.get("code"):
            # Do not echo arbitrary upstream messages: they may include user content or secrets.
            code = self.clean(str(data.get("code") or f"http_{response.status_code}"))
            messages = {
                401: "Model API Key is missing or rejected",
                403: "Access to this operation was denied",
                413: "Input exceeds the upstream size limit",
                429: "Upstream rate limit reached",
            }
            raise MediaError(
                code,
                messages.get(
                    response.status_code,
                    "Upstream rejected the request; inspect model parameters or trace ID",
                ),
                retryable=method == "GET" and response.status_code >= 500,
                request_id=self.clean(str(data.get("request_id") or request_id or "")),
            )
        return data
