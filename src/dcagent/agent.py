"""
dcagent agent — chat handlers, pipe listener, and full run_bot() implementation.

Importing this module patches dcagent.bot.run_bot with the full implementation
(message handlers + pipe listener). The entry point is main() which does that
patch then delegates to bot.main().

To use dcagent without the agent layer (bare event loop), run bot.main() directly.
"""

import logging
import os
import stat
import threading
import time
from typing import Optional

from deltachat2 import Bot, MsgData, Rpc, events

import dcagent.bot as _bot
from dcagent.bot import APP_NAME, AgentError, get_addrs

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipe listener
# ---------------------------------------------------------------------------


def _ensure_pipe(path: str) -> None:
    if os.path.exists(path):
        if not stat.S_ISFIFO(os.stat(path).st_mode):
            log.warning("%s exists but is not a FIFO — removing it", path)
            os.remove(path)
            os.mkfifo(path)
    else:
        os.mkfifo(path)


def _pipe_forward(text: str, accid: int, rpc: Rpc) -> None:
    """Forward a single text message to all alert chats."""
    chat_ids = _bot._get_alert_chats(rpc, accid)
    if not chat_ids:
        log.warning("pipe message received but no alert chats configured")
        return
    for chat_id in chat_ids:
        log.debug("Pipe message to alert channel %d: %r", chat_id, text[:80])
        rpc.send_msg(accid, chat_id, MsgData(text=text))


def _pipe_listener(path: str, accid: int, rpc: Rpc) -> None:
    """Blocking loop that reads plain-text lines from the named pipe and forwards each to all alert chats."""
    _ensure_pipe(path)
    log.info("Waiting for messages on %s", path)

    while True:
        with open(path) as pipe:
            for line in pipe:
                line = line.strip()
                if not line:
                    continue
                try:
                    _pipe_forward(line, accid, rpc)
                except Exception as exc:
                    log.exception("Error forwarding pipe message %r: %s", line, exc)
        log.debug("Pipe read eof, waiting for next writer")


# ---------------------------------------------------------------------------
# Chat handlers
# ---------------------------------------------------------------------------


def _on_new_message(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    if not msg.text:
        return

    if msg.chat_id in _bot._get_alert_chats(bot.rpc, accid):
        tag = "<alert>"
    elif msg.chat_id in _bot._get_admin_chats(bot.rpc, accid):
        tag = "<admin>"
    else:
        raise AgentError("Received message was neither from alert nor admin chat")

    bot.logger.info("Received message in chat %s %s: %r", msg.chat_id, tag, msg.text[:80])


def _on_help(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    bot.rpc.send_msg(
        accid,
        msg.chat_id,
        MsgData(text=f"👋 Hi! I am {APP_NAME}.\n\nCommands:\n  /help  – show this\n  /ping  – check I'm alive"),
    )


def _on_ping(bot: Bot, accid: int, event) -> None:
    bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="Pong! 🏓"))


# ---------------------------------------------------------------------------
# Full run_bot — overrides the default in bot.py
# ---------------------------------------------------------------------------


def run_bot(rpc: Rpc, accid: int, pipe_path: Optional[str] = None) -> None:
    """Full implementation: message handlers + optional pipe listener."""
    addrs = get_addrs(rpc, accid)
    log.info("Listening at: %s", ", ".join(addrs))

    hooks = [
        (_on_new_message, events.NewMessage(is_bot=None)),
        (_on_help, events.NewMessage(command="/help")),
        (_on_ping, events.NewMessage(command="/ping")),
    ]
    bot = Bot(rpc, hooks, logger=log)

    if pipe_path:
        t = threading.Thread(
            target=_pipe_listener,
            args=(pipe_path, accid, rpc),
            name="pipe-listener",
            daemon=True,
        )
        t.start()
        log.info("Pipe listener started on %s", pipe_path)

    while True:
        try:
            bot.run_forever(accid)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            log.exception("Event loop error: %s", exc)
            time.sleep(5)


# Patch the default run_bot in bot.py with this full implementation.
_bot.run_bot = run_bot


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: patches run_bot, then runs the standard CLI."""
    _bot.main()
