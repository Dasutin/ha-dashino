"""Config flow for Dashino."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BASE_URL,
    CONF_DEFAULT_SOURCE,
    CONF_DEFAULT_TYPE,
    CONF_DEFAULT_WIDGET_ID,
    CONF_SECRET,
    DOMAIN,
)
from .http_client import DashinoClient


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class DashinoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dashino."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            base_url_raw: str = user_input[CONF_BASE_URL]
            base_url = _normalize_base_url(base_url_raw)
            default_source: str = user_input[CONF_DEFAULT_SOURCE].strip()
            secret: str = user_input.get(CONF_SECRET, "")
            default_widget_id: str = user_input.get(CONF_DEFAULT_WIDGET_ID, "")
            default_type: str = user_input.get(CONF_DEFAULT_TYPE, "")

            if not _is_valid_url(base_url):
                errors[CONF_BASE_URL] = "invalid_url"
            elif not default_source:
                errors[CONF_DEFAULT_SOURCE] = "invalid_source"
            else:
                client = DashinoClient(
                    base_url=base_url,
                    default_source=default_source,
                    session=async_get_clientsession(self.hass),
                    secret=secret or None,
                )

                try:
                    await client.test_connectivity(default_source)
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"

            if not errors:
                data = {
                    CONF_BASE_URL: base_url,
                    CONF_DEFAULT_SOURCE: default_source,
                    CONF_SECRET: secret,
                    CONF_DEFAULT_WIDGET_ID: default_widget_id,
                    CONF_DEFAULT_TYPE: default_type,
                }
                return self.async_create_entry(title="Dashino", data=data)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
                vol.Required(CONF_DEFAULT_SOURCE, default="homeassistant"): str,
                vol.Optional(CONF_SECRET, default=""): str,
                vol.Optional(CONF_DEFAULT_WIDGET_ID, default=""): str,
                vol.Optional(CONF_DEFAULT_TYPE, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
