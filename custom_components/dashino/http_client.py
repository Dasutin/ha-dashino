"""HTTP client helper for Dashino."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_TIMEOUT


class DashinoClient:
    """Client for communicating with Dashino webhooks."""

    def __init__(
        self,
        *,
        base_url: str,
        default_source: str,
        session: ClientSession,
        secret: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_source = default_source
        self.session = session
        self.secret = secret
        self.timeout = timeout
        self.last_error: str | None = None

    def _webhook_url(self, source: str | None) -> str:
        src = source or self.default_source
        return f"{self.base_url}/api/webhooks/{src}"

    async def forward_webhook(self, *, source: str | None, payload: Any) -> None:
        """Send payload to Dashino webhook."""

        url = self._webhook_url(source)
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret

        timeout = ClientTimeout(total=self.timeout)

        async with self.session.post(
            url, json=payload, headers=headers, timeout=timeout
        ) as resp:
            await self._raise_for_status(resp)
            self.last_error = None

    async def _raise_for_status(self, response: ClientResponse) -> None:
        if 200 <= response.status < 300:
            return

        body = await response.text()
        snippet = body[:200] if body else ""
        self.last_error = f"Status {response.status}: {snippet}"
        raise HomeAssistantError(f"Dashino request failed ({response.status}): {snippet}")

    async def test_connectivity(self, source: str | None = None) -> None:
        """Perform a lightweight connectivity test."""

        test_payload = {"type": "dashino-test", "data": {"ok": True}}
        await self.forward_webhook(source=source, payload=test_payload)
