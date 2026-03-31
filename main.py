"""
Delta Chat Agent (dcagent)
--------------------------

Leverage BotCli for a simple DeltaChat chat bot.
Add a thread for listening to messages on unix pipe.
Add join commands to join existing chats (and for easy E2E testing)
"""

import json
import logging
import os
import stat
import sys
import threading
import time

from deltabot_cli import BotCli
from deltachat2 import CoreEvent, EventType, MsgData, events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BOT_NAME = "dcagent"

# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

cli = BotCli(DEFAULT_BOT_NAME)


@cli.on_start
def on_start(bot, args) -> None:
    """Launch the pipe listener thread."""

    if args.pipe:
        accid = bot.rpc.get_all_account_ids()[0]
        t = threading.Thread(target=_pipe_listener, args=(args.pipe, accid), name="pipe-listener", daemon=True)
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


def _pipe_listener(path: str, accid: int) -> None:
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
                    _dispatch(json.loads(raw), accid)
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON on pipe: %s — %s", raw, exc)
                except Exception as exc:
                    logger.exception("Error handling pipe command %r: %s", raw, exc)
        # Writer closed — loop back and wait for the next one.
        logger.debug("Pipe writer disconnected, waiting for next writer")


def _dispatch(cmd: dict, accid: int) -> None:
    """Route a parsed command dict to the appropriate handler."""
    kind = cmd.get("cmd")
    if kind == "send":
        _cmd_send(accid, cmd)
    else:
        logger.warning("Unknown pipe command: %r", kind)


def _cmd_send(accid: int, cmd: dict) -> None:
    """Handle {"cmd": "send", "chat_id": <int>, "text": "<str>"}."""
    chat_id = cmd.get("chat_id")
    text = cmd.get("text", "")

    if not isinstance(chat_id, int) or not text:
        logger.error("send command missing chat_id or text: %r", cmd)
        return

    # BotCli exposes no public send API, so we access rpc here via the private cli._bot
    cli._bot.rpc.send_msg(accid, chat_id, MsgData(text=text))  # noqa: SLF001
    logger.info("Sent message to chat %s: %r", chat_id, text[:80] + "...")


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

    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=msg.text))
    logger.info("Received message in chat %s: %r", msg.chat_id, msg.text[:80] + "...")


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
# Join subcommand
# ---------------------------------------------------------------------------

_JOIN_TIMEOUT = 60  # seconds to wait for SecureJoin handshake


def _join_cmd(_cli, bot, args) -> None:
    """Join an existing admin channel via a SecureJoin invite link.

    The resulting chat is saved as this bot's admin channel, replacing any
    previously configured admin chat. Prints the chat_id on success.
    """
    accid = args.account or bot.rpc.get_all_account_ids()[0]
    if not bot.rpc.is_configured(accid):
        logger.error("Account not configured")
        sys.exit(1)

    bot.rpc.start_io(accid)
    chat_id = bot.rpc.join_securejoin(accid, args.invite)
    logger.info("SecureJoin initiated (chat_id=%s), waiting for handshake…", chat_id)

    deadline = time.monotonic() + _JOIN_TIMEOUT
    while time.monotonic() < deadline:
        raw = bot.rpc.get_next_event()
        event = CoreEvent(raw.event)
        if event.kind == EventType.SECUREJOIN_JOINER_PROGRESS:
            logger.debug("SecureJoin progress: %s%%", event.progress // 10)
            if event.progress == 1000:
                break
            if event.progress == 0:
                logger.error("SecureJoin failed or was cancelled")
                sys.exit(1)
    else:
        logger.error("SecureJoin timed out after %ss", _JOIN_TIMEOUT)
        sys.exit(1)

    # ui.admin_chat is how BotCli identifies the admin chat and admins
    bot.rpc.set_config(accid, "ui.admin_chat", str(chat_id))
    logger.info("Joined admin channel (chat_id=%s)", chat_id)
    print(chat_id)


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

    join_parser = cli.add_subcommand(_join_cmd, name="join")
    join_parser.add_argument(
        "invite",
        metavar="INVITE",
        help="SecureJoin invite link (from 'dcagent admin' or 'dcagent link')",
    )

    cli.start()


if __name__ == "__main__":
    main()
