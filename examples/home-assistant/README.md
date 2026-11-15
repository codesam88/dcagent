# Home Assistant integration

Loopback-only HTTP bridge between Home Assistant and dcagent's named pipe.
The bridge runs on the same host as dcagent and listens on 127.0.0.1.

## Setup

1. Ensure dcagent service runs and creates its pipe (default `/run/dcagent/dcagent.pipe`).
2. Add your HA OS/user to the `dcagent` group so it can write the pipe:
   `sudo usermod -aG dcagent homeassistant` (or the user running HA).
   Pipe mode is `0620` (group-writable), never world-writable.
3. Copy `dcagent-ha-bridge.py` to `/etc/dcagent/ha-bridge.py` (or any path).
4. Provision the token — prefer a token file over an inline token, and never
   pass `--token` on the command line (it is visible in `ps`):
   `openssl rand -hex 32 > /etc/dcagent/ha-bridge.token`
   `chmod 600 /etc/dcagent/ha-bridge.token`
   Set `HA_BRIDGE_TOKEN_FILE=/etc/dcagent/ha-bridge.token` in
   `/etc/dcagent/ha-bridge.env` (`chmod 600 /etc/dcagent/ha-bridge.env`) or
   pass `--token-file /etc/dcagent/ha-bridge.token`.
5. Install systemd unit `dcagent-ha-bridge.service` (BindsTo=dcagent.service).
6. Add `rest_command.yaml` to HA configuration and automations from
   `automations.yaml`. `rest_command.yaml` loads the Authorization header from
   `secrets.yaml` via `!secret dcagent_auth_header` (see `secrets.yaml.example`);
   it must hold the same token as the bridge.

## Security notes

- Bridge binds to 127.0.0.1 only; never expose to LAN.
- Token file must be mode 0600; so must `/etc/dcagent/ha-bridge.env` if it
  contains a token. Do not pass `--token` on the command line (visible in `ps`).
- Pipe must never be world-writable (mode 0620, group dcagent).
- Category regex: `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$`.
- Messages are single line, stripped, max 500 chars.
- Status keys: no whitespace, max 64 chars.
- Request bodies are capped at 8192 bytes (larger requests get 400).
- Rate limits: one write per category for alerts, one per key for status,
  every 5 seconds.

## Category conventions

Use `ha-<domain>-<object>` for alerts, e.g. `ha-leak-kitchen`, `ha-smoke-living`.
Clear alerts by sending empty message (recovery path).

## Status example

Low-churn key example: `status 40_ha <value>`.

## MQTT alternative

See `mqtt-alternative.yaml` for publishing via MQTT to a subscriber that runs
`dcagent-send` (install it on PATH, e.g. `/usr/local/bin/dcagent-send`).
