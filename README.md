# dcagent

`dcagent` is a lightweight agent for monitoring Linux systems. It provides
out-of-band heartbeat and alerting for small or privately managed networks.

`dcagent` leverages the [Delta Chat](https://delta.chat) messaging system,
where accounts are free and nobody judges you for talking to bots.

**Features:**
- **Heartbeat** — bots can monitor each other over a dedicated channel
- **Alerts** — send notifications to an admin or group chat
- **Pipe relay** — local programs send messages via a Unix named pipe

## Command Reference

### CLI & Chat Commands

| Feature | CLI (bot.py) | Chat (agent.py) | Notes |
|---|---|---|---|
| Help | `-h` / `--help` | `/help` | |
| Version | `-v` / `--version` | `/version` | |
| Init account | `init ADDR [PASS]` | — | Register DC account |
| Config | `config [KEY [VAL]]` | — | Get/set DC account config |
| Admin chat | `admin [INVITE]` | `/admin [INVITE]` ★ | Print or join given invite for admin control |
| Alert chat | `alert [INVITE]` | `/alert [INVITE]` ★ | Print or join given invite for alert/notifications |
| Heartbeat chat | `heartbeat [INVITE]` | `/heartbeat [INVITE]` ★ | Print or join given invite for heartbeat protocol |
| Serve | `serve [opts]` | — | Start the agent (including pipe listener and heartbeat threads) |

### Additional Chat Commands

| Command | Syntax | Description |
| Echo test  | — | `/ping MSG` | Echo MSG back on same chat |
| List chats | — | `/chats` ★ | List managed chat IDs |
| Leave chat | — | `/leave CHATID` ★ | Leave and unregister a chat |

★ admin only

### Pipe Commands

The pipe is a write-only interface for external processes (e.g. monitoring scripts) running on the same host.
Commands are newline-delimited; each line starts with a command word followed by space-separated arguments.

| Command | Syntax | Description |
|---|---|---|
| `alert` | `alert <category> [message]` | Send message to all alert chats. See handling of alert messages for details. |
| `status` | `status <key> <value>` | Set bot status. See handling of bot status field for details. |
| `dcmsg` | `dcmsg <message>` | Send a raw message to all admin chats (only available in `--testmode`). |

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

Once the bot is running, chat commands are available. See [Command Reference](#command-reference) for the full list.

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

The agent can accept commands from a Unix named pipe.

Start the agent with `--pipe-path`:

```bash
uv run dcagent serve --pipe-path /tmp/dcagent.pipe
```

Then send commands to the pipe:

```bash
# Send an alert
echo "alert disk-usage-root disk 95% full" > /tmp/dcagent.pipe

# Clear an alert (sends recovery message on first clear)
echo "alert disk-usage-root" > /tmp/dcagent.pipe

# Update status
echo "status disk 95%" > /tmp/dcagent.pipe

# Send a message to admin chats (testmode only)
uv run dcagent serve --pipe-path /tmp/dcagent.pipe --testmode
# Then: echo "dcmsg Test message to admin" > /tmp/dcagent.pipe
```

**Handling of Status Inputs**

- `status` inputs are aggregated in a key-value dictionary
- The overall bot status is created by concatenating the list of status
  values, sorted based on their keys.

**Testmode**

The `--testmode` flag enables the `dcmsg` command for sending messages to admin chats.
This is useful for integration tests or manual testing of chat command handlers.

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
examples/actions/disk-space-alert > /run/dcagent/dcagent.pipe
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
| `DCAGENT_PIPE_PATH` | `/run/dcagent/dcagent.pipe` | Unix named pipe path for external commands |
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
They output alerts and status updates that can be fed to the pipe:

```bash
examples/actions/disk-space-alert > /run/dcagent/dcagent.pipe
```

### Usage

The unit runs as the `dcagent` user, restarts on failure, and listens on a Unix named pipe
for external commands.

Send alerts or status updates via the pipe:

```bash
echo "alert Disk /data is 95% full" > /run/dcagent/dcagent.pipe
echo "status 01_reboot [needs-reboot]" > /run/dcagent/dcagent.pipe
```

Check status and logs:

```bash
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
