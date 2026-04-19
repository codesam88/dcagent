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

from deltachat2 import Bot, MsgData, Rpc, events

import dcagent.bot as _bot
import dcagent.heartbeat as _heartbeat
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


def _pipe_do_alert(text: str, accid: int, rpc: Rpc) -> None:
    """Forward a single text message to all alert chats."""
    chat_ids = _bot._get_alert_chats(rpc, accid)
    if not chat_ids:
        log.warning("pipe message received but no alert chats configured")
        return
    for chat_id in chat_ids:
        log.debug("Pipe message to alert channel %d: %r", chat_id, text[:80])
        rpc.send_msg(accid, chat_id, MsgData(text=text))


def _pipe_do_status(args: str, accid: int, rpc: Rpc, status_map: dict) -> None:
    """Update status_map[key]=value and write space-joined values to selfstatus."""
    parts = args.split(None, 1)
    if len(parts) < 2:
        log.warning("pipe 'status' command requires a key and value, got: %r", args)
        return
    key, value = parts
    status_map[key] = value
    selfstatus = " ".join(v for _, v in sorted(status_map.items()))
    log.debug("Pipe status update: %s=%r -> selfstatus=%r", key, value, selfstatus)
    rpc.set_config(accid, "selfstatus", selfstatus)


def _pipe_dispatch(line: str, accid: int, rpc: Rpc, status_map: dict) -> None:
    """Parse and dispatch a single pipe line by its first word (command)."""
    cmd, _, args = line.partition(" ")
    args = args.strip()
    if cmd == "alert":
        _pipe_do_alert(args, accid, rpc)
    elif cmd == "status":
        _pipe_do_status(args, accid, rpc, status_map)
    else:
        log.warning("Unknown pipe command %r (line: %r)", cmd, line[:80])


def _pipe_listener(path: str, accid: int, rpc: Rpc, status_map: dict) -> None:
    """Blocking loop that reads command lines from the named pipe and dispatches them.

    Commands:
        alert <message>       forward message to all alert chats
        status <key> <msg>    update status element key to msg
    """
    _ensure_pipe(path)
    log.info("Waiting for messages on %s", path)

    while True:
        with open(path) as pipe:
            for line in pipe:
                line = line.strip()
                if not line:
                    continue
                try:
                    _pipe_dispatch(line, accid, rpc, status_map)
                except Exception as exc:
                    log.exception("Error handling pipe line %r: %s", line, exc)
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
    elif msg.chat_id in _bot._get_heartbeat_chats(bot.rpc, accid):
        tag = "<heartbeat>"
    else:
        log.debug("Received message from unknown chat %d, ignoring", msg.chat_id)
        return

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


def run_bot(
    rpc: Rpc,
    accid: int,
    pipe_path: str,
    heartbeat_interval: int,
    alert_dir: str = "",
    alert_interval: int = 60,
    status_dir: str = "",
    status_interval: int = 60,
) -> None:
    """Full implementation: message handlers + optional pipe listener + heartbeat."""
    addrs = get_addrs(rpc, accid)
    our_addr = addrs[0] if addrs else ""
    log.info("Listening at: %s", ", ".join(addrs))

    hb_state = _heartbeat.HeartbeatState(interval=heartbeat_interval)

    hooks = [
        (_on_new_message, events.NewMessage(is_bot=None)),
        (_on_help, events.NewMessage(command="/help")),
        (_on_ping, events.NewMessage(command="/ping")),
        (hb_state.make_handler(), events.NewMessage(is_bot=None)),
    ]
    bot = Bot(rpc, hooks, logger=log)

    if pipe_path:
        status_map: dict[str, str] = {}
        threading.Thread(
            target=_pipe_listener,
            args=(pipe_path, accid, rpc, status_map),
            name="pipe-listener",
            daemon=True,
        ).start()
        log.info("Pipe listener started on %s", pipe_path)

    if _bot._get_heartbeat_chats(rpc, accid):
        hb_state.start(rpc, accid, our_addr)

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
    # When running from a self-contained .pyz (shiv), deltachat-rpc-server is
    # bundled inside the extraction directory but not on PATH. Skip if already
    # findable; otherwise locate it via importlib.resources (the stdlib way to
    # find data files inside an installed package).
    import shutil

    if not shutil.which("deltachat-rpc-server"):
        try:
            import importlib.resources

            rpc_dir = str(importlib.resources.files("deltachat_rpc_server"))
            os.environ["PATH"] = rpc_dir + os.pathsep + os.environ.get("PATH", "")
        except (ImportError, TypeError):
            pass

    _bot.main()
