"""HTTP client helper for Dashino."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_SECRET_HEADER, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class DashinoRequestError(HomeAssistantError):
    """Raised when Dashino returns an error response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class DashinoClient:
    """Client for communicating with Dashino APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        default_source: str,
        session: ClientSession,
        secret: str | None = None,
        secret_header: str | None = None,
        api_token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_source = default_source
        self.session = session
        self.secret = secret
        self.secret_header = secret_header or DEFAULT_SECRET_HEADER
        self.api_token = api_token
        self.timeout = timeout
        self.last_error: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if self.secret:
            headers[self.secret_header] = self.secret
        return headers

    def _webhook_url(self, source: str | None) -> str:
        src = source or self.default_source
        return f"{self.base_url}/api/webhooks/{src}"

    def _state_url(self, key: str) -> str:
        return f"{self.base_url}/api/states/{key}/value"

    async def forward_webhook(self, *, source: str | None, payload: Any) -> None:
        """Send payload to Dashino webhook."""

        url = self._webhook_url(source)
        await self._request("post", url, json=payload)

    async def set_state_value(self, key: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """Set or merge a Dashino state value."""

        url = self._state_url(key)
        return await self._request("post", url, json=body)

    async def clear_state_value(self, key: str) -> None:
        """Clear a Dashino state value."""

        url = self._state_url(key)
        await self._request("delete", url)

    async def test_connectivity(self, *, source: str | None = None) -> None:
        """Perform a connectivity test via webhook."""

        test_payload = {"type": "dashino-test", "data": {"ok": True}}
        await self.forward_webhook(source=source, payload=test_payload)

    async def check_health(self) -> None:
        """Call Dashino health endpoint if available."""

        url = f"{self.base_url}/api/health"
        await self._request("get", url)

    async def check_state_api(self, *, test_key: str = "__ha_test", source: str = "homeassistant") -> None:
        """Verify state API by writing and cleaning a test key."""

        body = {"data": {"ok": True}, "merge": False, "source": source}
        await self.set_state_value(test_key, body)
        try:
            await self.clear_state_value(test_key)
        except DashinoRequestError as err:
            if err.status == 404:
                return
            raise

    async def _request(self, method: str, url: str, json: Any | None = None) -> Any:
        timeout = ClientTimeout(total=self.timeout)
        try:
            async with self.session.request(
                method, url, json=json, headers=self._headers(), timeout=timeout
            ) as resp:
                if 200 <= resp.status < 300:
                    if resp.content_type == "application/json":
                        return await resp.json()
                    await resp.read()
                    self.last_error = None
                    return None

                body = await resp.text()
                snippet = body[:200] if body else ""
                self.last_error = f"Status {resp.status}: {snippet}"
                msg = f"Dashino request failed ({resp.status}) to {url}: {snippet}"
                _LOGGER.exception(msg)
                raise DashinoRequestError(msg, status=resp.status)
        except HomeAssistantError:
            raise
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino request error to %s: %s", url, err)
            raise HomeAssistantError(f"Dashino request error: {err}") from err
