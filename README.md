# dc-agent

A simple Delta Chat echo bot built with the [JSON-RPC Python bindings](https://py.delta.chat/jsonrpc/install.html).

It echoes every message sent to it and also responds to `/help` and `/ping` commands.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

## Quick start

### 1. Install dependencies

```bash
uv sync
```

This installs `deltabot-cli`, `deltachat2`, and `deltachat-rpc-server` (the Delta Chat core binary).

### 2. Create a chatmail account for the bot

```bash
uv run dc-agent init DCACCOUNT:https://nine.testrun.org/new
```

> **Tip:** Replace `nine.testrun.org` with any other [chatmail relay](https://chatmail.at/relays) you prefer.
> You can also use a regular e-mail account:
> ```bash
> uv run dc-agent init --email bot@example.com --password MyPassword
> ```

### 3. Customise the bot's display name and status

Open `src/dc_echobot/bot.py` and change the `BOT_NAME` constant at the top:

```python
BOT_NAME = "My Awesome Bot"   # ← edit this
```

Then apply the name to the account:

```bash
uv run dc-echobot config displayname "My Awesome Bot"
uv run dc-echobot config selfstatus "I echo everything you say!"
```

Optionally set an avatar:

```bash
uv run dc-echobot config selfavatar ./avatar.png
```

### 4. Get the invite link

```bash
uv run dc-echobot link
```

Open the printed URL in your Delta Chat app (or scan the QR code in a browser) to start a chat with the bot.

### 5. Run the bot

```bash
uv run dc-echobot serve
```

Send a message to the bot in your Delta Chat app — it will echo it right back!

## Project structure

```
dc-echobot/
├── pyproject.toml          # project metadata and dependencies
├── README.md
└── src/
    └── dc_echobot/
        ├── __init__.py
        └── bot.py          # all bot logic lives here
```

## Customisation

| What | Where |
|---|---|
| Bot display name | `BOT_NAME` constant in `bot.py` |
| Add a new command | `@cli.on(events.NewMessage, command="/yourcommand")` decorator |
| React to group events | `@cli.on(events.MemberListChanged)` etc. |
| Full JSON-RPC API | [api.rs source](https://github.com/chatmail/core/blob/main/deltachat-jsonrpc/src/api.rs) / [TypeScript docs](https://js.jsonrpc.delta.chat/classes/RawClient.html) |

## Development

Run with verbose logging:

```bash
RUST_LOG=info uv run dc-echobot serve
```

## References

- [Write a Bot – bots.delta.chat](https://bots.delta.chat/quickstart.html)
- [deltabot-cli-py](https://github.com/deltachat-bot/deltabot-cli-py)
- [deltachat2 library](https://github.com/adbenitez/deltachat2)
- [Echo bot examples in multiple languages](https://github.com/deltachat-bot/echo)
