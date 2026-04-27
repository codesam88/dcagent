# dcagent

`dcagent` is a lightweight agent for monitoring Linux systems. It provides
out-of-band heartbeat and alerting for small or privately managed networks.

`dcagent` leverages the [Delta Chat](https://delta.chat) messaging system,
where accounts are free and nobody judges you for talking to bots.

**Features:**
- **Heartbeat** — bots can monitor each other over a dedicated channel
- **Alerts** — send notifications to an admin or group chat
- **Pipe relay** — local programs send messages via a Unix named pipe

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Quick start

### 1. Install dependencies

```bash
uv sync
```

### 2. Create a chatmail account for the agent

```bash
uv run dcagent init DCACCOUNT:https://nine.testrun.org/new
```

> **FYI:** Replace `nine.testrun.org` with any other
> [chatmail relay](https://chatmail.at/relays), or even a regular email account:
> ```bash
> uv run dcagent init bot@example.com MyPassword
> ```

### 3. Configure the agent

Set the display name and status:

```bash
uv run dcagent config displayname "My Agent"
uv run dcagent config selfstatus "Agent ready"
```

Optionally set an avatar:

```bash
uv run dcagent config selfavatar ./avatar.png
```

### 4. Setup Admin Channel (optional)

The `/admin` chat command manages admin group chats. Admins can use this command
to generate invite links to the bot's admin group chat. The group is named after
the bot (e.g. `My Agent admins`). Send `/admin` in a chat to get an invite link.

Alternatively, set up the admin channel via CLI:

```bash
uv run dcagent admin
```

All accounts present in any admin chat are considered admins. Multiple admin
chats are supported.

### 5. Start the agent

```bash
uv run dcagent serve
```

Send a message to the agent in your Delta Chat app — it will echo it right back!

Once the bot is running, admins can use chat commands:
- `/help` — shows available commands
- `/version` — shows dcagent version
- `/chats` — lists managed alert and admin chats
- `/alert` — join or create an alert chat
- `/leave <chatid>` — leave a managed chat

### 6. Set up alert recipients (optional)

Alert chats receive all notifications from monitoring scripts. Admins can use the
`/alert` chat command to create or join alert chats. The bot's alert group is
typically named after the bot (e.g. `My Agent alerts`).

### 7. Set up heartbeat monitoring (optional)

Multiple agents can monitor each other's liveness by joining a shared heartbeat
group. Use the `/heartbeat` chat command (admin only) to create or join a
heartbeat chat. Once connected, agents periodically broadcast heartbeats. If a
node stops responding, the master node sends an offline alert to all alert chats.
Recovery is also detected and alerted. See [docs/heartbeat.md](docs/heartbeat.md)
for the full protocol spec.

### 8. Send external commands

The agent can accept commands from a Unix domain socket or TCP socket.

Start with `--listen-socket` for a Unix socket (recommended for local use):

```bash
uv run dcagent serve --listen-socket /tmp/dcagent.sock
```

Or `--listen-addr` for TCP (useful for network access):

```bash
uv run dcagent serve --listen-addr 127.0.0.1:9999
```

Or both simultaneously:

```bash
uv run dcagent serve --listen-socket /tmp/dcagent.sock --listen-addr 127.0.0.1:9999
```

Then send commands via `nc` (netcat):

```bash
# Via Unix socket
echo "alert disk-usage-root disk 95% full" | nc -U /tmp/dcagent.sock

# Via TCP
echo "alert disk-usage-root disk 95% full" | nc 127.0.0.1 9999

# Clear an alert (sends recovery message on first clear)
echo "alert disk-usage-root" | nc -U /tmp/dcagent.sock

# Immediate alert without deduplication (category "")
echo "alert '' CRITICAL: System overheating!" | nc -U /tmp/dcagent.sock

# Update status
echo "status disk 95%" | nc -U /tmp/dcagent.sock
```

**Handling of Status Inputs**

- `status` inputs are aggregated in a key-value dictionary
- The overall bot status is created by concatenating the list of status
  values, sorted based on their keys.

**Handling of Alert Inputs**

- `alert` inputs are deduplicated per category — repeating messages are ignored
- An empty category ("") is always sent immediately, without deduplication
- Transitioning from non-empty to empty message is called 'recovery' and causes
  the agent to send a special message: `<category>: recovered (was: <previous message>)`

Since categories are included with the alert and recovery messages, they should
be human-readable and the message should avoid repeating information already
contained in the category. For instance, a temperature-alarm script can use the
individual sensor names as part of the category, thus supporting
multiple/parallel alarm types.

```bash
examples/actions/disk-space-alert | nc -U /run/dcagent/dcagent.sock
```

## Deployment

To run dcagent as a system service, use the provided `setup.sh` helper.

### Install

```bash
# Clone or download the repo, then:
sudo examples/systemd/setup.sh
```

The script downloads the latest release binary for your architecture from the
[releases page](../../releases), creates a dedicated system user, installs the
systemd unit and environment file, creates a chatmail account, and prints the
admin group invite link.

To use a locally built binary instead:

```bash
make dist
make install   # calls setup.sh --pyz dist/dcagent-<arch>.pyz
```

Pass `--launch` to enable and start the service immediately:

```bash
sudo examples/systemd/setup.sh --launch
```

### Uninstall

```bash
sudo examples/systemd/setup.sh --uninstall
```

This stops and disables the service, removes the binary and systemd unit, and
deletes the `dcagent` user. The configuration directory `/etc/dcagent/` is
preserved (it may contain your alert and status scripts).

### Configuration

The service reads environment variables from `$DCAGENT_CONFIG_PATH/dcagent.conf`; action scripts may also load per-script overrides from `$DCAGENT_CONFIG_PATH/conf.d/<script>.conf`.

Key settings:

| Variable | Default | Description |
|---|---|---|
| `DCAGENT_CONFIG_PATH` | `/etc/dcagent` | Root config directory containing `dcagent.conf`, `conf.d/`, `actions/`, and `cron/` |
| `DCAGENT_LISTEN_SOCKET` | `/run/dcagent/dcagent.sock` | Unix domain socket path |
| `DCAGENT_LISTEN_ADDR` | (disabled) | TCP socket address (host:port format) |
| `DCAGENT_HEARTBEAT` | `60` | Heartbeat broadcast interval (seconds) |
| `DCAGENT_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |

### Action scripts

Action scripts live under `$DCAGENT_CONFIG_PATH/actions` and can read optional per-script config from `$DCAGENT_CONFIG_PATH/conf.d/`.
`dcagent-run-actions` batch-runs the dcagent user's crontab and is used by the service to refresh alerts and status on startup.

See `examples/README.md` and `examples/actions/README.md` for the scheduling layout and helper details.

Place executable scripts in `$DCAGENT_CONFIG_PATH/actions` and enable them for a
given interval by creating a symlink into the desired cron interval directory,
for example:

```bash
ln -s "$DCAGENT_CONFIG_PATH/actions/security-updates-alert" "$DCAGENT_CONFIG_PATH/cron/hourly.d/"
```

Action scripts should write single-line commands to stdout:

```bash
#!/usr/bin/env bash
echo 'alert my_alert something went wrong'
echo "status my_key some value"
```

Ready-made example scripts are in `examples/actions/`.
They can also be run standalone by piping to the socket:

```bash
examples/actions/disk-space-alert | nc -U /run/dcagent/dcagent.sock
```

### Usage

The unit runs as the `dcagent` user, restarts on failure, and exposes sockets
for external commands.

Send alerts or status updates directly via socket:

```bash
# Unix socket
echo "alert Disk /data is 95% full" | nc -U /run/dcagent/dcagent.sock
echo "status 01_reboot [needs-reboot]" | nc -U /run/dcagent/dcagent.sock

# Or via TCP if configured
echo "alert Disk /data is 95% full" | nc 127.0.0.1 9999
```

Check status and logs:

```bash
dcagent status
systemctl status dcagent
journalctl -u dcagent -f
```

## Development

## Components

- **`src/dcagent/`** — package source: `agent.py` (runtime, socket listeners, chat handlers), `bot.py` (CLI, account lifecycle), `heartbeat.py` (heartbeat protocol)
- **`tests/`** — unit tests (pytest + mocks) and integration tests
- **`docs/`** — protocol and feature documentation
- **`examples/`** — monitoring scripts for alerts and status, plus systemd service setup
- **`pyproject.toml`** / **`Makefile`** — project config and developer shortcuts

### Useful commands

The most common commands are wrapped into makefile helpers:

| Command      | Purpose |
|--------------|---------|
| `make run`   | Start the agent |
| `make check` | Run linter, pytest, and pre-commit hooks |
| `make test`  | Run all tests (check + integration tests) |
| `make format`| Format code with ruff |
| `make clean` | Remove build/cache artifacts |
| `make help`  | Show all targets |


You can look them up in the Makefile and call directly, e.g.:

```bash
# Run the agent
uv run dcagent serve

# Run with verbose logging
uv run dcagent --log-level debug serve

# Enable deltachat core (Rust) debug output
RUST_LOG=debug uv run dcagent serve

# Run tests
uv run pytest -v

# Run linter
uv run ruff check

# Format code
uv run ruff format
```


## References

- [Write a Bot – bots.delta.chat](https://bots.delta.chat/quickstart.html)
- [deltabot-cli-py](https://github.com/deltachat-bot/deltabot-cli-py)
- [deltachat2 library](https://github.com/adbenitez/deltachat2)
- [Echo bot examples in multiple languages](https://github.com/deltachat-bot/echo)
