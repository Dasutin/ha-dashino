"""Diagnostics support for Dashino."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import diagnostics
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_BASE_URL,
    CONF_DEFAULT_SOURCE,
    CONF_DEFAULT_TYPE,
    CONF_DEFAULT_WIDGET_ID,
    CONF_SECRET,
    DOMAIN,
)


def _redact_secret(value: str | None) -> str | None:
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

    return {
        "config": {
            CONF_BASE_URL: entry.data.get(CONF_BASE_URL),
            CONF_DEFAULT_SOURCE: entry.data.get(CONF_DEFAULT_SOURCE),
            CONF_DEFAULT_WIDGET_ID: entry.data.get(CONF_DEFAULT_WIDGET_ID) or None,
            CONF_DEFAULT_TYPE: entry.data.get(CONF_DEFAULT_TYPE) or None,
            CONF_SECRET: _redact_secret(entry.data.get(CONF_SECRET)),
        },
        "state": {
            "last_error": last_error,
        },
    }
