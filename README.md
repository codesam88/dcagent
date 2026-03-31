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
> uv run dcagent init --email bot@example.com --password MyPassword
> ```
> For other options see `uv run dcagent --help` or `uv run dcagent init --help`

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

### 4. Get the invite link

```bash
uv run dcagent link
```

Open the printed URL in your Delta Chat app (or scan the QR code in a browser)
to start a chat with the agent.

### 5. Setup Admin Channel (optional)

Create invite to admin channel or join existing via invite. Contacts on admin
channel are conidered admins. However, we don't tie any special functions to
this as of now.

```bash
uv run dcagent admin  # print admin-channel invite, or
uv run dcagent join <invite-link> # join existing channel
```

### 6. Start the agent

```bash
uv run dcagent serve
```

Send a message to the agent in your Delta Chat app — it will echo it right back!

### 7. Send external commands

The agent can accept commands from a Unix named pipe. Start with the `--pipe` option:

```bash
uv run dcagent serve --pipe /tmp/dcagent.pipe
```

Then send commands:

```bash
echo '{"cmd": "send", "chat_id": 12, "text": "alert!"}' > /tmp/dcagent.pipe
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
RUST_LOG=info uv run dcagent serve

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
