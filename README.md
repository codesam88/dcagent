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

The `alert` command manages the bot's alert group — a group chat that receives
all pipe notifications. Without an invite, it prints an invite link to that group:

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

The `admin` command manages admin group chats. Without an invite, it prints an
invite link to the bot's admin group:

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

### 7. Send external commands

The agent can accept commands from a Unix named pipe. Start with the `--pipe` option:

```bash
uv run dcagent serve --pipe /tmp/dcagent.pipe
```

Then send commands:

```bash
echo "alert!" > /tmp/dcagent.pipe
```

## Development

## Project Structure

```
dcagent/
├── main.py           # Single-file bot (all logic here)
├── test_dcagent.py   # Pytest test suite
├── pyproject.toml    # Project config, dependencies, ruff settings
├── Makefile          # Developer shortcuts
├── README.md         # User documentation
├── AGENTS.md         # This file - agent guidance
└── uv.lock
```

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
