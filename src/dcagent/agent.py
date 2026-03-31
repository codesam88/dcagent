"""
dcagent agent — chat handlers, pipe listener, and full run_bot() implementation.

Importing this module patches dcagent.bot.run_bot with the full implementation
(message handlers + pipe listener). The entry point is main() which does that
patch then delegates to bot.main().

To use dcagent without the agent layer (bare event loop), run bot.main() directly.
"""

import json
import logging
import os
import stat
import threading
import time
from typing import Optional

from deltachat2 import Bot, MsgData, Rpc, events

import dcagent.bot as _bot
from dcagent.bot import APP_NAME, get_addrs

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


def _pipe_listener(path: str, accid: int, rpc: Rpc) -> None:
    """Blocking loop that reads newline-delimited JSON commands from the named pipe."""
    _ensure_pipe(path)
    log.info("Waiting for commands on %s", path)

    while True:
        with open(path) as pipe:
            for raw in pipe:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    _dispatch(json.loads(raw), accid, rpc)
                except json.JSONDecodeError as exc:
                    log.error("Invalid JSON on pipe: %s — %s", raw, exc)
                except Exception as exc:
                    log.exception("Error handling pipe command %r: %s", raw, exc)
        log.debug("Pipe writer disconnected, waiting for next writer")


def _dispatch(cmd: dict, accid: int, rpc: Rpc) -> None:
    kind = cmd.get("cmd")
    if kind == "send":
        _pipe_send(accid, cmd, rpc)
    else:
        log.warning("Unknown pipe command: %r", kind)


def _pipe_send(accid: int, cmd: dict, rpc: Rpc) -> None:
    """Handle {"cmd": "send", "chat_id": <int>, "text": "<str>"}."""
    chat_id = cmd.get("chat_id")
    text = cmd.get("text", "")
    if not isinstance(chat_id, int) or not text:
        log.error("send command missing chat_id or text: %r", cmd)
        return
    rpc.send_msg(accid, chat_id, MsgData(text=text))
    log.info("Sent message to chat %s: %r", chat_id, text[:80])


# ---------------------------------------------------------------------------
# Chat handlers
# ---------------------------------------------------------------------------


def _on_new_message(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    if not msg.text:
        return
    bot.logger.info("Received message in chat %s: %r", msg.chat_id, msg.text[:80])


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
