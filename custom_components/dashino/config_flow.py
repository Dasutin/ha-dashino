"""Config flow for Dashino."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
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
    DOMAIN,
)
from .http_client import DashinoClient, DashinoRequestError


def _normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _build_schema(current: dict[str, Any] | None = None) -> vol.Schema:
    cur = current or {}
    return vol.Schema(
        {
            vol.Required(CONF_BASE_URL, default=cur.get(CONF_BASE_URL, "")): str,
            vol.Required(
                CONF_DEFAULT_SOURCE,
                default=cur.get(CONF_DEFAULT_SOURCE, DEFAULT_SOURCE_VALUE),
            ): str,
            vol.Optional(CONF_DEFAULT_STATE_KEY, default=cur.get(CONF_DEFAULT_STATE_KEY, "")):
                str,
            vol.Optional(CONF_API_TOKEN, default=cur.get(CONF_API_TOKEN, "")): str,
            vol.Optional(CONF_SECRET, default=cur.get(CONF_SECRET, "")): str,
            vol.Optional(
                CONF_SECRET_HEADER, default=cur.get(CONF_SECRET_HEADER, DEFAULT_SECRET_HEADER)
            ): str,
            vol.Optional(CONF_DEFAULT_WIDGET_ID, default=cur.get(CONF_DEFAULT_WIDGET_ID, "")):
                str,
            vol.Optional(CONF_DEFAULT_TYPE, default=cur.get(CONF_DEFAULT_TYPE, "")): str,
        }
    )


async def _validate_and_normalize(
    hass, user_input: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}

    base_url_raw: str = user_input[CONF_BASE_URL]
    base_url = _normalize_base_url(base_url_raw)
    default_source: str = user_input.get(CONF_DEFAULT_SOURCE, DEFAULT_SOURCE_VALUE).strip()
    default_source = default_source or DEFAULT_SOURCE_VALUE
    default_state_key: str = user_input.get(CONF_DEFAULT_STATE_KEY, "").strip()
    api_token: str = user_input.get(CONF_API_TOKEN, "").strip()
    secret: str = user_input.get(CONF_SECRET, "").strip()
    secret_header: str = (
        user_input.get(CONF_SECRET_HEADER, DEFAULT_SECRET_HEADER).strip() or DEFAULT_SECRET_HEADER
    )
    default_widget_id: str = user_input.get(CONF_DEFAULT_WIDGET_ID, "").strip()
    default_type: str = user_input.get(CONF_DEFAULT_TYPE, "").strip()

    if not _is_valid_url(base_url):
        errors[CONF_BASE_URL] = "invalid_url"
    if not default_source:
        errors[CONF_DEFAULT_SOURCE] = "invalid_source"

    if errors:
        return {}, errors

    client = DashinoClient(
        base_url=base_url,
        default_source=default_source,
        session=async_get_clientsession(hass),
        secret=secret or None,
        secret_header=secret_header or DEFAULT_SECRET_HEADER,
        api_token=api_token or None,
    )

    health_missing = False
    try:
        await client.check_health()
    except DashinoRequestError as err:
        if err.status == 404:
            health_missing = True
        else:
            errors["base"] = "cannot_connect"
    except Exception:  # noqa: BLE001
        errors["base"] = "cannot_connect"

    if not errors and health_missing:
        try:
            await client.check_state_api(source=default_source)
        except DashinoRequestError as err:
            if err.status == 404:
                errors["base"] = "state_api_missing"
            else:
                errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "cannot_connect"

    normalized = {
        CONF_BASE_URL: base_url,
        CONF_DEFAULT_SOURCE: default_source,
        CONF_DEFAULT_STATE_KEY: default_state_key,
        CONF_API_TOKEN: api_token,
        CONF_SECRET: secret,
        CONF_SECRET_HEADER: secret_header,
        CONF_DEFAULT_WIDGET_ID: default_widget_id,
        CONF_DEFAULT_TYPE: default_type,
    }

    return normalized, errors


class DashinoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dashino."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            normalized, errors = await _validate_and_normalize(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="Dashino", data=normalized)

        data_schema = _build_schema()
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfigure to update entry without removal."""

        entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        if entry is None:
            return self.async_abort(reason="unknown_entry")

        errors: dict[str, str] = {}

        if user_input is not None:
            normalized, errors = await _validate_and_normalize(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(entry, data=normalized, options={})
                return self.async_abort(reason="reconfigure_successful")

        current = entry.options or entry.data
        data_schema = _build_schema(current)
        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )


class DashinoOptionsFlowHandler(OptionsFlow):
    """Handle Dashino options."""

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized, errors = await _validate_and_normalize(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="Dashino", data=normalized)

        current = self.entry.options or self.entry.data
        data_schema = _build_schema(current)

        return self.async_show_form(step_id="init", data_schema=data_schema, errors=errors)


async def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
    """Create the options flow."""

    return DashinoOptionsFlowHandler(entry)
