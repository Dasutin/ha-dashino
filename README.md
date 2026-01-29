# Dashino Home Assistant Integration

Dashino is a lightweight Home Assistant integration that forwards automation payloads to a Dashino server via its webhook endpoint. It exposes a single service action (`dashino.forward`) that you can call from automations or scripts. No entities are created.

## Features
- UI-based config flow with single-instance enforcement
- Normalizes Dashino base URL and optional webhook secret header
- Optional defaults for `source`, `widgetId`, and `type`
- Single service to post arbitrary or templated payloads to `POST <base_url>/api/webhooks/<source>`
- Diagnostics with secret redaction

## Requirements
- Dashino server reachable from Home Assistant
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
   - **Dashino Base URL** (e.g., `http://192.168.1.50:4040`; trailing slash will be stripped)
   - **Default source** (path segment for the webhook, e.g., `homeassistant`)
   - **X-Webhook-Secret** (optional; header sent only when provided)
   - Optional defaults for **widgetId** and **type**
3. The flow posts a small test payload to the webhook; any 2xx response is treated as success.

Only one Dashino configuration entry is allowed.

## Service: `dashino.forward`
Posts a JSON payload to `POST <base_url>/api/webhooks/<source>`.

### Fields
- `source` (string, optional): Overrides configured default source
- `widgetId` (string, optional): Widget identifier
- `type` (string, optional): Message type
- `data` (any, optional): Arbitrary payload placed under `data`
- `raw` (any, optional): Full JSON body to send; when provided, other fields are ignored

### Body construction
- If `raw` is provided: body = `raw`
- Else: body includes provided `widgetId`, `type`, `data`. If nothing is set, body defaults to `{ "type": "dashino-forward", "data": {} }`.

### Examples
Forward a toast to widget `alerts` with templated message:
```yaml
service: dashino.forward
data:
  widgetId: alerts
  type: toast
  data:
    message: "{{ states('sensor.living_room_status') }}"
```

Send a fully custom raw payload:
```yaml
service: dashino.forward
data:
  raw:
    widgetId: camera-feed
    type: refresh
    data:
      reason: manual
```

## Diagnostics
Available from the integration entry; secrets are redacted. Includes last error seen by the client and stored defaults.

## Notes
- Timeouts default to 10 seconds.
- On non-2xx responses, the service raises `HomeAssistantError` with status and a snippet of the response body.
