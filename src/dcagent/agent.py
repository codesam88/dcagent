"""
dcagent agent — chat handlers, socket listener, and full run_bot() implementation.

Importing this module patches dcagent.bot.run_bot with the full implementation
(message handlers + socket listener). The entry point is main() which does that
patch then delegates to bot.main().

To use dcagent without the agent layer (bare event loop), run bot.main() directly.
"""

import logging
import os
import stat
import threading
import time
from datetime import datetime

from deltachat2 import Bot, MsgData, Rpc, events

import dcagent.bot as _bot
import dcagent.heartbeat as _heartbeat
from dcagent.bot import APP_NAME, get_addrs

log = logging.getLogger(__name__)

# Module-level flag for test mode (set by run_bot)
_testmode = False


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


def _handle_alert_state(category: str, message: str, alert_map: dict[str, str]) -> str | None:
    """
    Determine if alert should be sent based on state transition.

    Returns formatted message to send (or None if nothing to send).
    Does NOT update alert_map - caller must do that after sending.

    Logic:
    - category "": always send (bypass deduplication)
    - message != previous: send new message
    - message == "" and previous != "": send recovery message
    - otherwise: send nothing
    """
    if category == "":
        return message

    prev_message = alert_map.get(category, "")

    if message != prev_message:
        if message == "" and prev_message != "":
            return f"{category}: recovered (was: {prev_message})"
        elif message != "":
            return f"{category}: {message}"

    return None


def _pipe_do_alert(args: str, accid: int, rpc: Rpc, alert_map: dict[str, str]) -> None:
    """Handle alert command: parse category and message, apply state logic, send if needed."""
    parts = args.split(None, 1)
    if len(parts) < 1:
        log.warning("pipe 'alert' command requires category, got empty string")
        return

    category = parts[0]
    message = parts[1] if len(parts) > 1 else ""

    message_to_send = _handle_alert_state(category, message, alert_map)

    if message_to_send is None:
        log.debug("Alert suppressed (no state change): category=%r, message=%r", category, message)
        return

    chat_ids = _bot._get_alert_chats(rpc, accid)
    if not chat_ids:
        log.warning("pipe alert received but no alert chats configured")
        return

    for chat_id in chat_ids:
        log.debug("Pipe alert to channel %d: %r", chat_id, message_to_send[:80])
        rpc.send_msg(accid, chat_id, MsgData(text=message_to_send))

    alert_map[category] = message


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


def _pipe_do_dcmsg(args: str, accid: int, rpc: Rpc) -> None:
    """Send a message to all admin chats. Only available in testmode."""
    global _testmode
    if not _testmode:
        log.warning("dcmsg command requires --testmode")
        return
    if not args:
        log.warning("pipe 'dcmsg' command requires a message")
        return
    admin_chats = _bot._get_admin_chats(rpc, accid)
    if not admin_chats:
        log.warning("No admin chats configured for dcmsg")
        return
    for chat_id in admin_chats:
        rpc.send_msg(accid, chat_id, MsgData(text=args))
    log.debug("dcmsg sent to %d admin chat(s)", len(admin_chats))


def _pipe_dispatch(line: str, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> None:
    """Parse and dispatch a single pipe line by its first word (command)."""
    cmd, _, args = line.partition(" ")
    args = args.strip()
    if cmd == "alert":
        _pipe_do_alert(args, accid, rpc, alert_map)
    elif cmd == "status":
        _pipe_do_status(args, accid, rpc, status_map)
    elif cmd == "dcmsg":
        _pipe_do_dcmsg(args, accid, rpc)
    else:
        log.warning("Unknown pipe command %r (line: %r)", cmd, line[:80])


def _pipe_listener(path: str, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> None:
    """Blocking loop that reads command lines from the named pipe and dispatches them."""
    _ensure_pipe(path)
    log.info("Waiting for messages on %s", path)

    while True:
        with open(path) as pipe:
            for line in pipe:
                line = line.strip()
                if not line:
                    continue
                try:
                    _pipe_dispatch(line, accid, rpc, status_map, alert_map)
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
    bot_name = bot.rpc.get_config(accid, "displayname") or APP_NAME
    help_text = (
        f"👋 Hi! I am {bot_name}.\n\n"
        "Commands:\n"
        "  /help       – show this\n"
        "  /ping       – check I'm alive\n"
        "  /version    – show dcagent version\n"
        "  /alert      – manage alert chat (admin only)\n"
        "  /admin      – manage admin chat (admin only)\n"
        "  /heartbeat  – manage heartbeat chat (admin only)\n"
        "  /chats      – list managed chats (admin only)\n"
        "  /leave      – leave a chat (admin only)"
    )
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=help_text))


def _on_ping(bot: Bot, accid: int, event) -> None:
    bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="Pong! 🏓"))


def _on_version(bot: Bot, accid: int, event) -> None:
    """Handle /version command: show dcagent version."""
    version = _bot._get_version()
    bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text=f"dcagent {version}"))


def _on_alert(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    # Check if sender is in admin chat
    if msg.chat_id not in _bot._get_admin_chats(bot.rpc, accid):
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Only admins can use /alert"))
        return

    # Extract invite from message text if provided
    # Format: "/alert [<invite>]"
    parts = msg.text.strip().split(None, 1)
    invite = parts[1] if len(parts) > 1 else None

    try:
        if not invite:
            # Generate and send alert chat invite
            chatid = _bot._get_or_create_alert_chat(bot.rpc, accid)
            qr_code = bot.rpc.get_chat_securejoin_qr_code(accid, chatid)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"Alert chat invite:\n{qr_code}"))
        else:
            # Join alert chat from invite
            chat_id = _bot._securejoin(bot.rpc, accid, invite)
            _bot._add_alert_chat(bot.rpc, accid, chat_id)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"✓ Joined alert chat (chat_id={chat_id})"))
    except Exception as e:
        log.exception("Error handling /alert command")
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"❌ Error: {e}"))


def _on_admin(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    # Check if sender is in admin chat
    if msg.chat_id not in _bot._get_admin_chats(bot.rpc, accid):
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Only admins can use /admin"))
        return

    # Extract invite from message text if provided
    # Format: "/admin [<invite>]"
    parts = msg.text.strip().split(None, 1)
    invite = parts[1] if len(parts) > 1 else None

    try:
        if not invite:
            # Generate and send admin chat invite
            chatid = _bot._get_or_create_admin_chat(bot.rpc, accid)
            qr_code = bot.rpc.get_chat_securejoin_qr_code(accid, chatid)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"Admin chat invite:\n{qr_code}"))
        else:
            # Join admin chat from invite
            chat_id = _bot._securejoin(bot.rpc, accid, invite)
            _bot._add_admin_chat(bot.rpc, accid, chat_id)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"✓ Joined admin chat (chat_id={chat_id})"))
    except Exception as e:
        log.exception("Error handling /admin command")
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"❌ Error: {e}"))


def _on_chats(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    # Check if sender is in admin chat
    if msg.chat_id not in _bot._get_admin_chats(bot.rpc, accid):
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Only admins can use /chats"))
        return

    admin_chats = _bot._get_admin_chats(bot.rpc, accid)
    alert_chats = _bot._get_alert_chats(bot.rpc, accid)
    heartbeat_chats = _bot._get_heartbeat_chats(bot.rpc, accid)

    lines = ["Managed chats:"]
    if admin_chats:
        lines.append("Admin:")
        for cid in admin_chats:
            lines.append(f"  {cid}")
    if alert_chats:
        lines.append("Alert:")
        for cid in alert_chats:
            lines.append(f"  {cid}")
    if heartbeat_chats:
        lines.append("Heartbeat:")
        for cid in heartbeat_chats:
            lines.append(f"  {cid}")
    if not admin_chats and not alert_chats and not heartbeat_chats:
        lines.append("(none)")

    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="\n".join(lines)))


def _on_heartbeat(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    if msg.chat_id not in _bot._get_admin_chats(bot.rpc, accid):
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Only admins can use /heartbeat"))
        return

    # Format: "/heartbeat [<invite>]"
    parts = msg.text.strip().split(None, 1)
    invite = parts[1] if len(parts) > 1 else None

    try:
        if not invite:
            # Generate and send heartbeat chat invite
            chatid = _bot._get_or_create_heartbeat_chat(bot.rpc, accid)
            qr_code = bot.rpc.get_chat_securejoin_qr_code(accid, chatid)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"Heartbeat chat invite:\n{qr_code}"))
        else:
            # Join heartbeat chat from invite
            chat_id = _bot._securejoin(bot.rpc, accid, invite)
            _bot._add_heartbeat_chat(bot.rpc, accid, chat_id)
            bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"✓ Joined heartbeat chat (chat_id={chat_id})"))
    except Exception as e:
        log.exception("Error handling /heartbeat command")
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"❌ Error: {e}"))


def _on_leave(bot: Bot, accid: int, event) -> None:
    msg = event.msg
    # Check if sender is in admin chat
    if msg.chat_id not in _bot._get_admin_chats(bot.rpc, accid):
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Only admins can use /leave"))
        return

    # Extract chat_id from message text
    # Format: "/leave <chatid>"
    parts = msg.text.strip().split(None, 1)
    if len(parts) < 2:
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="Usage: /leave <chatid>"))
        return

    try:
        chat_id = int(parts[1])
    except ValueError:
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="❌ Invalid chat ID"))
        return

    try:
        # Remove from admin/alert lists
        admin_chats = _bot._get_admin_chats(bot.rpc, accid)
        alert_chats = _bot._get_alert_chats(bot.rpc, accid)

        if chat_id in admin_chats:
            admin_chats.remove(chat_id)
            bot.rpc.set_config(accid, "ui.admin_chats", ",".join(str(c) for c in admin_chats))
        if chat_id in alert_chats:
            alert_chats.remove(chat_id)
            bot.rpc.set_config(accid, "ui.alert_chats", ",".join(str(c) for c in alert_chats))

        # Leave the chat
        bot.rpc.remove_contact_from_chat(accid, chat_id, 1)  # 1 is self contact id
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"✓ Left chat {chat_id}"))
    except Exception as e:
        log.exception("Error handling /leave command")
        bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=f"❌ Error: {e}"))


# ---------------------------------------------------------------------------
# Full run_bot — overrides the default in bot.py
# ---------------------------------------------------------------------------


def _report_config(
    addrs: list,
    pipe_path: str,
    heartbeat_interval: int,
    testmode: bool,
) -> None:
    """Log active configuration at INFO level on startup."""
    log.info("Listening at: %s", ", ".join(addrs))
    log.info("Heartbeat interval: %ds", heartbeat_interval)
    log.info("Pipe listener: %s", pipe_path if pipe_path else "disabled")
    if testmode:
        log.warning("Test mode enabled (dcmsg pipe command active)")


def run_bot(
    rpc: Rpc,
    accid: int,
    pipe_path: str = "",
    heartbeat_interval: int = 60,
    alert_dir: str = "",
    alert_interval: int = 60,
    status_dir: str = "",
    status_interval: int = 60,
    testmode: bool = False,
) -> None:
    """Full implementation: message handlers + optional pipe listener + heartbeat."""
    global _testmode
    _testmode = testmode

    addrs = get_addrs(rpc, accid)
    our_addr = addrs[0] if addrs else ""
    _report_config(addrs, pipe_path, heartbeat_interval, testmode)

    hb_state = _heartbeat.HeartbeatState(interval=heartbeat_interval)

    hooks = [
        (_on_new_message, events.NewMessage(is_bot=None)),
        (_on_help, events.NewMessage(command="/help")),
        (_on_ping, events.NewMessage(command="/ping")),
        (_on_version, events.NewMessage(command="/version")),
        (_on_alert, events.NewMessage(command="/alert")),
        (_on_admin, events.NewMessage(command="/admin")),
        (_on_heartbeat, events.NewMessage(command="/heartbeat")),
        (_on_chats, events.NewMessage(command="/chats")),
        (_on_leave, events.NewMessage(command="/leave")),
        (hb_state.make_handler(), events.NewMessage(is_bot=None)),
    ]
    bot = Bot(rpc, hooks, logger=log)

    status_map: dict[str, str] = {}
    alert_map: dict[str, str] = {}

    if pipe_path:
        threading.Thread(
            target=_pipe_listener,
            args=(pipe_path, accid, rpc, status_map, alert_map),
            name="pipe-listener",
            daemon=True,
        ).start()

    bot_name = rpc.get_config(accid, "displayname") or APP_NAME
    hb_state.start(rpc, accid, f"{our_addr}({bot_name})")

    # Send startup message to alert chats
    chat_ids = _bot._get_alert_chats(rpc, accid)
    if chat_ids:
        startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        startup_msg = f"{bot_name} started at {startup_time}"
        for chat_id in chat_ids:
            rpc.send_msg(accid, chat_id, MsgData(text=startup_msg))

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
