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

### 4. Set up alert recipients

The `alert` command manages the bot's alert group — a group chat named after
the bot (e.g. `My Agent alerts`) that receives all pipe notifications. Without
an invite, it prints an invite link to that group:

```bash
uv run dcagent alert
```

Share the printed link with anyone who should receive alerts. When they scan it,
they join the bot's alert group chat. Alternatively, have the bot join a chat
defined by the user by passing their invite link:

```bash
uv run dcagent alert <invite-link>
```

All alert chats (whether created here or joined via invite) will receive every
message sent through the pipe.

### 5. Setup Admin Channel (optional)

The `admin` command manages admin group chats. The group is named after the bot
(e.g. `My Agent admins`). Without an invite, it prints an invite link to the
bot's admin group:

```bash
uv run dcagent admin
```

Alternatively, have the bot join an admin channel defined by the user:

```bash
uv run dcagent admin <invite-link>
```

All accounts present in any admin chat are considered admins. Multiple admin
chats are supported.

### 6. Start the agent

```bash
uv run dcagent serve
```

Send a message to the agent in your Delta Chat app — it will echo it right back!

Use `status` at any time to see the current account and invite links:

```bash
uv run dcagent status
```

### 7. Set up heartbeat monitoring (optional)

The `heartbeat` command manages heartbeat group chats (named e.g. `My Agent heartbeat`).
Multiple agents can join the same heartbeat group to monitor each other's liveness.
Without an invite, it prints an invite link to the bot's heartbeat group:

```bash
uv run dcagent heartbeat
```

Have another agent join the heartbeat group:

```bash
uv run dcagent heartbeat <invite-link>
```

Once serving, agents periodically broadcast heartbeats. If a node stops
responding, the elected master node sends an offline alert to all alert chats.
Recovery is also detected and alerted. See [docs/heartbeat.md](docs/heartbeat.md)
for the full protocol spec.

### 8. Send external commands

The agent can accept commands from a Unix named pipe. Start with the `--pipe-path` option:

```bash
uv run dcagent serve --pipe-path /tmp/dcagent.pipe
```

Then send commands:

```bash
# Alert with category and message (sent if state changes)
echo "alert disk-usage-root disk 95% full" > /tmp/dcagent.pipe

# Clear an alert (sends recovery message on first clear)
echo "alert disk-usage-root" > /tmp/dcagent.pipe

# Immediate alert without deduplication (category "")
echo "alert '' CRITICAL: System overheating!" > /tmp/dcagent.pipe

# Update status
echo "status disk 95%" > /tmp/dcagent.pipe
```

**Alert behavior:**
- Alerts are deduplicated per category — alerts only send if the message changes
- Empty message (or omitted) marks the category as recovered and clears the alert
- On first recovery, dcagent sends: `<category>: recovered (was: <previous message>)`
- Category "" (empty string) always sends immediately without deduplication
- Categories should use dashes as word separators (e.g., `disk-usage-root`, `security-updates`, `temperature-acpi-core0`)

Action scripts write their output to stdout; redirect to the pipe when running standalone:

```bash
examples/actions/disk-space-alert >> /run/dcagent/dcagent.pipe
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
systemd unit and environment file, creates a chatmail account, and prints
invite links for the alert, heartbeat, and admin groups.

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
| `DCAGENT_PIPE_PATH` | `/run/dcagent/dcagent.pipe` | Unix named pipe path |
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
echo "alert ⚠️ something went wrong"
echo "status my_key some value"
```

Ready-made example scripts are in `examples/actions/`.
They can also be run standalone by redirecting to the pipe:

```bash
examples/actions/disk-space-alert >> /run/dcagent/dcagent.pipe
```

### Usage

The unit runs as the `dcagent` user, restarts on failure, and exposes a pipe
at `/run/dcagent/dcagent.pipe` for external commands.

Send alerts or status updates directly via the pipe:

```bash
echo "alert Disk /data is 95% full"    > /run/dcagent/dcagent.pipe
echo "status 01_reboot [needs-reboot]" > /run/dcagent/dcagent.pipe
```

Check status and logs:

```bash
dcagent status
systemctl status dcagent
journalctl -u dcagent -f
```

## Development

## Components

- **`src/dcagent/`** — package source: `agent.py` (runtime, pipe listener, chat handlers), `bot.py` (CLI, account lifecycle), `heartbeat.py` (heartbeat protocol)
- **`tests/`** — unit tests (pytest + mocks) and integration tests
- **`docs/`** — protocol and feature documentation
- **`examples/`** — monitoring scripts for alerts and status, plus systemd service setup
- **`pyproject.toml`** / **`Makefile`** — project config and developer shortcuts

### Useful commands

The most common commands are wrapped into makefile helpers:

| Command      | Purpose |
|--------------|---------|
| `make run`   | Start the agent |
| `make test`  | Run all tests (linter, pytest, pre-commit) |
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
