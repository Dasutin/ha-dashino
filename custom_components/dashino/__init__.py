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
    ATTR_ENTITY_ID,
    ATTR_FIELD,
    ATTR_KEY,
    ATTR_MERGE,
    ATTR_MAP,
    ATTR_RAW,
    ATTR_REPLACE,
    ATTR_ATTRIBUTE,
    ATTR_AS_NUMBER,
    ATTR_ROUND,
    ATTR_SOURCE,
    ATTR_TYPE,
    ATTR_WIDGET_ID,
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_DEFAULT_SOURCE,
    CONF_DEFAULT_STATE_KEY,
    CONF_DEFAULT_TYPE,
    CONF_DEFAULT_WIDGET_ID,
    CONF_SECRET,
    CONF_SECRET_HEADER,
    DEFAULT_SECRET_HEADER,
    DEFAULT_SOURCE_VALUE,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .http_client import DashinoClient, DashinoRequestError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data to the latest version."""

    if entry.version == 1:
        data = {**entry.data}
        data.setdefault(CONF_SECRET_HEADER, "X-Webhook-Secret")
        data.setdefault(CONF_API_TOKEN, "")
        data.setdefault(CONF_DEFAULT_STATE_KEY, "")
        data.setdefault(CONF_DEFAULT_SOURCE, data.get(CONF_DEFAULT_SOURCE) or DEFAULT_SOURCE_VALUE)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dashino from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    def _get(key: str) -> str | None:
        return entry.options.get(key, entry.data.get(key))

    base_url: str = _get(CONF_BASE_URL) or ""
    default_source: str = _get(CONF_DEFAULT_SOURCE) or DEFAULT_SOURCE_VALUE
    default_state_key: str | None = _get(CONF_DEFAULT_STATE_KEY) or None
    secret_value = _get(CONF_SECRET)
    secret: str | None = secret_value or None
    secret_header: str = _get(CONF_SECRET_HEADER) or DEFAULT_SECRET_HEADER
    api_token: str | None = _get(CONF_API_TOKEN) or None
    default_widget_id: str | None = _get(CONF_DEFAULT_WIDGET_ID) or None
    default_type: str | None = _get(CONF_DEFAULT_TYPE) or None

    client = DashinoClient(
        base_url=base_url,
        default_source=default_source,
        secret=secret,
        secret_header=secret_header,
        api_token=api_token,
        session=async_get_clientsession(hass),
        timeout=DEFAULT_TIMEOUT,
    )

    service_schema_forward = vol.Schema(
        {
            vol.Optional(ATTR_SOURCE): cv.string,
            vol.Optional(ATTR_WIDGET_ID): cv.string,
            vol.Optional(ATTR_TYPE): cv.string,
            vol.Optional(ATTR_DATA): vol.Any(dict, list, str, int, float, bool, None),
            vol.Optional(ATTR_RAW): vol.Any(dict, list, str, int, float, bool, None),
        }
    )

    service_schema_set_state = vol.Schema(
        {
            vol.Optional(ATTR_KEY): cv.string,
            vol.Optional(ATTR_DATA): vol.Any(dict, list, str, int, float, bool, None),
            vol.Optional(ATTR_MERGE): cv.boolean,
            vol.Optional(ATTR_REPLACE): cv.boolean,
            vol.Optional(ATTR_SOURCE): cv.string,
            vol.Optional(ATTR_RAW): vol.Any(dict, list, str, int, float, bool, None),
        }
    )

    service_schema_set_state_field = vol.Schema(
        {
            vol.Optional(ATTR_KEY): cv.string,
            vol.Required(ATTR_FIELD): cv.string,
            vol.Required(ATTR_ENTITY_ID): cv.entity_id,
            vol.Optional(ATTR_ATTRIBUTE): cv.string,
            vol.Optional(ATTR_MERGE): cv.boolean,
            vol.Optional(ATTR_SOURCE): cv.string,
            vol.Optional(ATTR_AS_NUMBER): cv.boolean,
            vol.Optional(ATTR_ROUND): vol.Coerce(int),
            vol.Optional(ATTR_MAP): dict,
        }
    )

    service_schema_clear_state = vol.Schema(
        {
            vol.Optional(ATTR_KEY): cv.string,
            vol.Optional(ATTR_SOURCE): cv.string,
        }
    )

    async def forward_service(call: ServiceCall) -> None:
        """Forward the payload to Dashino (legacy)."""

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
        except DashinoRequestError as err:
            raise HomeAssistantError(err.args[0]) from err
        except asyncio.TimeoutError as err:
            _LOGGER.exception("Dashino forward timed out: %s", err)
            raise HomeAssistantError("Dashino forward timed out") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino forward failed: %s", err)
            raise HomeAssistantError("Dashino forward failed") from err

    async def set_state_service(call: ServiceCall) -> None:
        """Set or merge a Dashino state."""

        key = call.data.get(ATTR_KEY) or default_state_key
        if not key:
            raise HomeAssistantError("Dashino state key is required")

        source_value = call.data.get(ATTR_SOURCE) or default_source or DEFAULT_SOURCE_VALUE
        raw = call.data.get(ATTR_RAW)

        if raw is not None:
            body = raw
        else:
            data_value = call.data.get(ATTR_DATA)
            if data_value is None:
                data_value = {}
            replace_value = call.data.get(ATTR_REPLACE)
            merge_value = call.data.get(ATTR_MERGE)
            merge = True
            if replace_value is True:
                merge = False
            elif merge_value is not None:
                merge = bool(merge_value)

            body = {"data": data_value, "merge": merge, "source": source_value}

        try:
            await client.set_state_value(key, body)
        except DashinoRequestError as err:
            raise HomeAssistantError(err.args[0]) from err
        except asyncio.TimeoutError as err:
            _LOGGER.exception("Dashino set_state timed out: %s", err)
            raise HomeAssistantError("Dashino set_state timed out") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino set_state failed: %s", err)
            raise HomeAssistantError("Dashino set_state failed") from err

    async def set_state_field_service(call: ServiceCall) -> None:
        """Set a single field in a Dashino state from an entity value."""

        key = call.data.get(ATTR_KEY) or default_state_key
        if not key:
            raise HomeAssistantError("Dashino state key is required")

        field_name = call.data.get(ATTR_FIELD)
        if not field_name:
            raise HomeAssistantError("Dashino field is required")

        entity_id = call.data.get(ATTR_ENTITY_ID)
        if not entity_id:
            raise HomeAssistantError("Dashino entity_id is required")

        state = hass.states.get(entity_id)
        if state is None:
            raise HomeAssistantError(f"Entity '{entity_id}' not found")

        attribute_name = call.data.get(ATTR_ATTRIBUTE)
        if attribute_name:
            if attribute_name not in state.attributes:
                raise HomeAssistantError(
                    f"Attribute '{attribute_name}' not found on entity '{entity_id}'"
                )
            value: Any = state.attributes.get(attribute_name)
        else:
            value = state.state

        map_table = call.data.get(ATTR_MAP)
        if isinstance(map_table, dict) and isinstance(value, str) and value in map_table:
            value = map_table[value]

        as_number = call.data.get(ATTR_AS_NUMBER, False)
        round_digits = call.data.get(ATTR_ROUND)
        if as_number:
            try:
                value = float(value)
            except (TypeError, ValueError) as err:
                raise HomeAssistantError(
                    f"Value for entity '{entity_id}' is not numeric and cannot be converted"
                ) from err
            if round_digits is not None:
                value = round(value, round_digits)

        merge_value = call.data.get(ATTR_MERGE)
        merge = True if merge_value is None else bool(merge_value)
        source_value = call.data.get(ATTR_SOURCE) or default_source or DEFAULT_SOURCE_VALUE

        body = {"data": {field_name: value}, "merge": merge, "source": source_value}

        try:
            await client.set_state_value(key, body)
        except DashinoRequestError as err:
            raise HomeAssistantError(err.args[0]) from err
        except asyncio.TimeoutError as err:
            _LOGGER.exception("Dashino set_state_field timed out: %s", err)
            raise HomeAssistantError("Dashino set_state_field timed out") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino set_state_field failed: %s", err)
            raise HomeAssistantError("Dashino set_state_field failed") from err

    async def clear_state_service(call: ServiceCall) -> None:
        """Clear a Dashino state."""

        key = call.data.get(ATTR_KEY) or default_state_key
        if not key:
            raise HomeAssistantError("Dashino state key is required")

        try:
            await client.clear_state_value(key)
        except DashinoRequestError as err:
            raise HomeAssistantError(err.args[0]) from err
        except asyncio.TimeoutError as err:
            _LOGGER.exception("Dashino clear_state timed out: %s", err)
            raise HomeAssistantError("Dashino clear_state timed out") from err
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Dashino clear_state failed: %s", err)
            raise HomeAssistantError("Dashino clear_state failed") from err

    hass.services.async_register(
        DOMAIN,
        "forward",
        forward_service,
        schema=service_schema_forward,
    )

    hass.services.async_register(
        DOMAIN,
        "set_state",
        set_state_service,
        schema=service_schema_set_state,
    )

    hass.services.async_register(
        DOMAIN,
        "set_state_field",
        set_state_field_service,
        schema=service_schema_set_state_field,
    )

    hass.services.async_register(
        DOMAIN,
        "clear_state",
        clear_state_service,
        schema=service_schema_clear_state,
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
    for service in ("forward", "set_state", "set_state_field", "clear_state"):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
