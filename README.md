# Dashino Home Assistant Integration

Dashino now supports first-class state updates. Home Assistant automations can push state data to Dashino’s State API (`POST <base_url>/api/states/:key/value`), which Dashino rebroadcasts as SSE events (`state:<key>`) and persists for widgets. The legacy webhook forwarder remains for compatibility.

## Features
- UI-based config flow (single instance)
- Optional auth: Bearer token or Dashino secret header (default `X-Dashino-Secret`)
- Defaults for state key and source, plus legacy widget/type defaults
- Primary services: `dashino.set_state` (update/merge/replace) and `dashino.clear_state`
- Legacy webhook forwarding (`dashino.forward`) kept for existing automations
- Diagnostics with auth redaction

## Requirements
- Dashino server reachable from Home Assistant
- Dashino version with State API (`/api/states/...`) recommended
- Home Assistant 2023.12+ (tested on core; should work on newer versions)

## Installation
### HACS (recommended)
1. In HACS, add this repository as a custom integration repository.
2. Install **Dashino** from HACS.
3. Restart Home Assistant.

### Manual
1. Copy the `custom_components/dashino` folder into your Home Assistant `config/custom_components` directory.
2. Restart Home Assistant.

## Configuration
1. Go to *Settings → Devices & Services → Add Integration* and search for **Dashino**.
2. Enter:
   - **Dashino Base URL** (e.g., `http://192.168.1.50:4040`; trailing slash is stripped)
   - **Default source** (used in state payloads; default `homeassistant`)
   - **Default state key** (optional fallback when a service call omits `key`)
   - **Dashino API token** (optional; sent as `Authorization: Bearer ...`)
   - **Dashino secret** and optional **Secret header name** (default `X-Dashino-Secret`)
   - Legacy defaults (optional): **widgetId**, **type** for webhook forwarding
3. Connectivity check: tries `/api/health` or posts a test state; surfaces an error if the Dashino State API is missing.

Only one Dashino configuration entry is allowed.

## Services
### `dashino.set_state` (preferred)
Posts to `POST <base_url>/api/states/<key>/value`.

Fields:
- `key` (string, optional): State key; falls back to configured default key.
- `data` (any, optional): JSON payload; defaults to `{}` when omitted and no `raw` is provided.
- `merge` (bool, optional): Merge into existing state (default true).
- `replace` (bool, optional): Forces `merge=false` when true.
- `source` (string, optional): Label for the update; defaults to configured source.
- `raw` (any, optional): Full body to send; ignores other fields when provided.

Examples:
- Merge forecast data:
  ```yaml
  service: dashino.set_state
  data:
    key: forecast
    data:
      temperature: "{{ state_attr('weather.home','temperature') }}"
      summary: "{{ states('weather.home') }}"
  ```
- Replace a state entirely:
  ```yaml
  service: dashino.set_state
  data:
    key: forecast
    replace: true
    data:
      temperature: 21
      summary: clear
  ```

### `dashino.clear_state`
Deletes a Dashino state key via `DELETE <base_url>/api/states/<key>/value`.

Example:
```yaml
service: dashino.clear_state
data:
  key: forecast
```

### `dashino.forward` (legacy)
Legacy webhook forwarder to `POST <base_url>/api/webhooks/<source>`. Prefer `dashino.set_state` for new automations.

## Diagnostics
Available from the integration entry; auth values are redacted. Includes last error seen by the client and stored defaults.

## Notes
- Timeouts default to 10 seconds.
- On non-2xx responses, services raise `HomeAssistantError` with status, URL, and a snippet of the response body.
