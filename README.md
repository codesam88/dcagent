# dcagent

A Delta Chat agent that echoes messages and accepts external commands via a Unix named pipe.

## Features

- **Echo bot**: Responds with the same text it receives
- **Commands**: `/help` and `/ping` supported
- **External control**: Accepts JSON commands via Unix named pipe for automation

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Quick start

### 1. Install dependencies

```bash
uv sync
```

This installs `deltabot-cli`, `deltachat2`, and `deltachat-rpc-server` (the Delta Chat core binary).

### 2. Create a chatmail account for the agent

```bash
uv run dcagent init DCACCOUNT:https://nine.testrun.org/new
```

> **Tip:** Replace `nine.testrun.org` with any other [chatmail relay](https://chatmail.at/relays) you prefer.
> You can also use a regular e-mail account:
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

Open the printed URL in your Delta Chat app (or scan the QR code in a browser) to start a chat with the agent.

### 5. Start the agent

```bash
uv run dcagent serve
```

Send a message to the agent in your Delta Chat app — it will echo it right back!

### 6. Send external commands

The agent can accept commands from a Unix named pipe. Start with the `--pipe` option:

```bash
uv run dcagent serve --pipe /tmp/dcagent.pipe
```

Then send commands:

```bash
echo '{"cmd": "send", "chat_id": 12, "text": "alert!"}' > /tmp/dcagent.pipe
```

## Customisation

| What | Where |
|------|-------|
| Agent display name | `DEFAULT_BOT_NAME` constant in `main.py` (line 44) |
| Add a new command | `@cli.on(events.NewMessage, command="/yourcommand")` decorator |
| React to group events | `@cli.on(events.MemberListChanged)` etc. |
| Full JSON-RPC API | [api.rs source](https://github.com/deltachat/core/blob/main/deltachat-jsonrpc/src/api.rs) / [TypeScript docs](https://js.jsonrpc.delta.chat/classes/RawClient.html) |

## Development

### Project structure

```
dcagent/
├── main.py         # Single-file bot with all logic
├── pyproject.toml  # Python project config + ruff linting
└── README.md       # This file
```

### Useful commands

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
