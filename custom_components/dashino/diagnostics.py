"""Diagnostics support for Dashino."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import diagnostics
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_DEFAULT_SOURCE,
    CONF_DEFAULT_STATE_KEY,
    CONF_DEFAULT_TYPE,
    CONF_DEFAULT_WIDGET_ID,
    CONF_SECRET,
    CONF_SECRET_HEADER,
    DOMAIN,
)


def _redact(value: str | None) -> str | None:
    if not value:
        return None
    return diagnostics.REDACTED


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    client = stored.get("client")
    last_error = getattr(client, "last_error", None)

    conf = entry.options or entry.data

    return {
        "config": {
            CONF_BASE_URL: conf.get(CONF_BASE_URL),
            CONF_DEFAULT_SOURCE: conf.get(CONF_DEFAULT_SOURCE),
            CONF_DEFAULT_STATE_KEY: conf.get(CONF_DEFAULT_STATE_KEY) or None,
            CONF_DEFAULT_WIDGET_ID: conf.get(CONF_DEFAULT_WIDGET_ID) or None,
            CONF_DEFAULT_TYPE: conf.get(CONF_DEFAULT_TYPE) or None,
            CONF_SECRET: _redact(conf.get(CONF_SECRET)),
            CONF_SECRET_HEADER: conf.get(CONF_SECRET_HEADER),
            CONF_API_TOKEN: _redact(conf.get(CONF_API_TOKEN)),
        },
        "state": {
            "last_error": last_error,
        },
    }
