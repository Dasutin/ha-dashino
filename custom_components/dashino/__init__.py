"""Dashino integration setup."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_DATA,
    ATTR_RAW,
    ATTR_SOURCE,
    ATTR_TYPE,
    ATTR_WIDGET_ID,
    CONF_BASE_URL,
    CONF_DEFAULT_SOURCE,
    CONF_DEFAULT_TYPE,
    CONF_DEFAULT_WIDGET_ID,
    CONF_SECRET,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .http_client import DashinoClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dashino from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    def _get(key: str) -> str | None:
        return entry.options.get(key, entry.data.get(key))

    base_url: str = _get(CONF_BASE_URL) or ""
    default_source: str = _get(CONF_DEFAULT_SOURCE) or ""
    secret_value = _get(CONF_SECRET)
    secret: str | None = secret_value or None
    default_widget_id: str | None = _get(CONF_DEFAULT_WIDGET_ID) or None
    default_type: str | None = _get(CONF_DEFAULT_TYPE) or None

    client = DashinoClient(
        base_url=base_url,
        default_source=default_source,
        secret=secret,
        session=async_get_clientsession(hass),
        timeout=DEFAULT_TIMEOUT,
    )

    service_schema = vol.Schema(
        {
            vol.Optional(ATTR_SOURCE): cv.string,
            vol.Optional(ATTR_WIDGET_ID): cv.string,
            vol.Optional(ATTR_TYPE): cv.string,
            vol.Optional(ATTR_DATA): vol.Any(dict, list, str, int, float, bool, None),
            vol.Optional(ATTR_RAW): vol.Any(dict, list, str, int, float, bool, None),
        }
    )

    async def forward_service(call: ServiceCall) -> None:
        """Forward the payload to Dashino."""

        source = call.data.get(ATTR_SOURCE) or default_source
        if not source:
            raise HomeAssistantError("Dashino source is required")

        body: Any
        if ATTR_RAW in call.data:
            body = call.data[ATTR_RAW]
        else:
            body = {}
            widget_id = call.data.get(ATTR_WIDGET_ID) or default_widget_id
            msg_type = call.data.get(ATTR_TYPE) or default_type
            data = call.data.get(ATTR_DATA)

            if widget_id is not None:
                body[ATTR_WIDGET_ID] = widget_id
            if msg_type is not None:
                body[ATTR_TYPE] = msg_type
            if data is not None:
                body[ATTR_DATA] = data

            if not body:
                body = {"type": "dashino-forward", "data": {}}

        try:
            await client.forward_webhook(source=source, payload=body)
        except HomeAssistantError:
            raise
        except asyncio.TimeoutError as err:
            _LOGGER.exception("Dashino forward timed out: %s", err)
            raise HomeAssistantError("Dashino forward timed out") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino forward failed: %s", err)
            raise HomeAssistantError("Dashino forward failed") from err

    hass.services.async_register(
        DOMAIN,
        "forward",
        forward_service,
        schema=service_schema,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "service_registered": True,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dashino config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, "forward"):
        hass.services.async_remove(DOMAIN, "forward")

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
