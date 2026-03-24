"""
Delta Chat Agent (dcagent)
--------------------------
An echo bot that also accepts commands from an external Unix named pipe,
allowing other processes to trigger outbound messages and commands.

Usage
-----
# One-time setup: create a random chatmail account and set name/status
uv run dcagent init DCACCOUNT:https://nine.testrun.org/new
uv run dcagent config displayname "My Agent"
uv run dcagent config selfstatus "I am an agent."

# Get the invite link for connecting (control channel)
uv run dcagent link

# Start the bot (pipe is created automatically at runtime)
uv run dcagent serve

Pipe command format (one JSON object per line)
----------------------------------------------
{"cmd": "send", "chat_id": 12, "text": "Hello from outside!"}

Example
-------
echo '{"cmd": "send", "chat_id": 12, "text": "alert!"}' > /tmp/dcagent.pipe
"""

import json
import logging
import os
import stat
import threading

from deltabot_cli import BotCli
from deltachat2 import MsgData, events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BOT_NAME = "dcagent"

# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

cli = BotCli("dcagent")


@cli.on_start
def on_start(bot, args) -> None:
    """Launch the pipe listener thread."""

    if args.pipe:
        t = threading.Thread(target=_pipe_listener, args=(args.pipe,), name="pipe-listener", daemon=True)
        t.start()
        logger.info("Pipe listener started on %s", args.pipe)


# ---------------------------------------------------------------------------
# Pipe listener
# ---------------------------------------------------------------------------


def _ensure_pipe(path: str) -> None:
    """Create the named pipe if it doesn't exist, remove a regular file if it does."""
    if os.path.exists(path):
        if not stat.S_ISFIFO(os.stat(path).st_mode):
            logger.warning("%s exists but is not a FIFO — removing it", path)
            os.remove(path)
            os.mkfifo(path)
    else:
        os.mkfifo(path)


def _pipe_listener(path: str) -> None:
    """
    Blocking loop that reads newline-delimited JSON commands from the named pipe.

    Opening a FIFO for reading blocks until a writer connects, which is the
    desired behaviour — the thread simply waits.  When the writer closes its
    end the read loop gets EOF; we reopen to wait for the next writer.
    """
    _ensure_pipe(path)
    logger.info("Waiting for commands on %s", path)

    while True:
        # Open blocks until at least one writer has the pipe open.
        with open(path) as pipe:
            for raw in pipe:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    _dispatch(json.loads(raw))
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON on pipe: %s — %s", raw, exc)
                except Exception as exc:
                    logger.exception("Error handling pipe command %r: %s", raw, exc)
        # Writer closed — loop back and wait for the next one.
        logger.debug("Pipe writer disconnected, waiting for next writer")


def _dispatch(cmd: dict) -> None:
    """Route a parsed command dict to the appropriate handler."""
    kind = cmd.get("cmd")
    if kind == "send":
        _cmd_send(cmd)
    else:
        logger.warning("Unknown pipe command: %r", kind)


def _cmd_send(cmd: dict) -> None:
    """Handle {"cmd": "send", "chat_id": <int>, "text": "<str>"}."""
    chat_id = cmd.get("chat_id")
    text = cmd.get("text", "")

    if not isinstance(chat_id, int) or not text:
        logger.error("send command missing chat_id or text: %r", cmd)
        return

    rpc = cli._bot.rpc  # noqa: SLF001
    accid = rpc.get_all_account_ids()[0]
    rpc.send_msg(accid, chat_id, MsgData(text=text))
    logger.info("Sent message to chat %s: %r", chat_id, text[:80])


# ---------------------------------------------------------------------------
# Incoming Delta Chat message handlers
# ---------------------------------------------------------------------------


@cli.on(events.NewMessage)
def on_new_message(bot, accid: int, event) -> None:
    """Echo every incoming message back to the sender."""
    msg = event.msg

    # Ignore messages sent by the bot itself and empty messages
    if not msg.text or msg.is_bot:
        return

    logger.info("Received message in chat %s: %r", msg.chat_id, msg.text[:80])
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=msg.text))


@cli.on(events.NewMessage(command="/help"))
def on_help(bot, accid: int, event) -> None:
    """Reply to /help with a short usage description."""
    msg = event.msg
    help_text = (
        f"👋 Hi! I am {DEFAULT_BOT_NAME}.\n\n"
        "I will echo back any message you send me.\n\n"
        "Commands:\n"
        "  /help  – show this message\n"
        "  /ping  – check that I'm alive\n"
    )
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=help_text))


@cli.on(events.NewMessage(command="/ping"))
def on_ping(bot, accid: int, event) -> None:
    """Reply to /ping with a pong."""
    msg = event.msg
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="Pong! 🏓"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cli.add_generic_option(
        "--pipe",
        metavar="PATH",
        help="path to the Unix named pipe for external commands (default: %(default)s)",
    )

    cli.start()


if __name__ == "__main__":
    main()
