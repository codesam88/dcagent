"""
dcagent agent — chat handlers, socket listener, and full run_bot() implementation.

Importing this module patches dcagent.bot.run_bot with the full implementation
(message handlers + socket listener). The entry point is main() which does that
patch then delegates to bot.main().

To use dcagent without the agent layer (bare event loop), run bot.main() directly.
"""

import logging
import os
import socket
import stat
import threading
import time
from datetime import datetime

from deltachat2 import Bot, MsgData, Rpc, events

import dcagent.bot as _bot
import dcagent.heartbeat as _heartbeat
from dcagent.bot import APP_NAME, get_addrs

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Socket listener
# ---------------------------------------------------------------------------


def _ensure_unix_socket(path: str) -> None:
    if os.path.exists(path):
        if not stat.S_ISSOCK(os.stat(path).st_mode):
            log.warning("%s exists but is not a socket — removing it", path)
            os.remove(path)
        else:
            os.remove(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


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


def _socket_do_alert(args: str, accid: int, rpc: Rpc, alert_map: dict[str, str]) -> str:
    """Handle alert command: parse category and message, apply state logic, send if needed."""
    parts = args.split(None, 1)
    if len(parts) < 1:
        return "error: alert command requires category"

    category = parts[0]
    message = parts[1] if len(parts) > 1 else ""

    message_to_send = _handle_alert_state(category, message, alert_map)

    if message_to_send is None:
        log.debug("Alert suppressed (no state change): category=%r, message=%r", category, message)
        return "ok: alert suppressed (no state change)"

    chat_ids = _bot._get_alert_chats(rpc, accid)
    if not chat_ids:
        return "error: no alert chats configured"

    for chat_id in chat_ids:
        log.debug("Socket alert to channel %d: %r", chat_id, message_to_send[:80])
        rpc.send_msg(accid, chat_id, MsgData(text=message_to_send))

    alert_map[category] = message
    return "ok: alert sent"


def _socket_do_status(args: str, accid: int, rpc: Rpc, status_map: dict) -> str:
    """Update status_map[key]=value and write space-joined values to selfstatus."""
    parts = args.split(None, 1)
    if len(parts) < 2:
        return "error: status command requires a key and value"
    key, value = parts
    status_map[key] = value
    selfstatus = " ".join(v for _, v in sorted(status_map.items()))
    log.debug("Socket status update: %s=%r -> selfstatus=%r", key, value, selfstatus)
    rpc.set_config(accid, "selfstatus", selfstatus)
    return "ok: status updated"


def _socket_do_config(args: str, accid: int, rpc: Rpc) -> str:
    """Get or set configuration values, or dump all config when no args."""
    parts = args.split(None, 1)

    # No args: print version, account info, and all config keys/values
    if not parts or not parts[0]:
        try:
            version = _bot._get_version()
            configured = rpc.is_configured(accid)
            addr = rpc.get_config(accid, "addr") or "(no address)"
            displayname = rpc.get_config(accid, "displayname") or ""
            name_part = f" ({displayname})" if displayname else ""
            status = "configured" if configured else "not configured"

            output = [
                f"dcagent {version}",
                f"Account #{accid}: {addr}{name_part} [{status}]",
            ]

            # Dump all config keys
            keys = rpc.get_config(accid, "sys.config_keys") or ""
            if keys:
                for key in keys.split():
                    value = rpc.get_config(accid, key)
                    output.append(f"{key}={value!r}")

            return "ok: " + "\n".join(output)
        except Exception as exc:
            log.exception("Config dump error: %s", exc)
            return f"error: config dump error: {exc}"

    # With args: get or set specific key
    key = parts[0]
    value = parts[1] if len(parts) > 1 else None
    try:
        if value is not None:
            rpc.set_config(accid, key, value)
        result = rpc.get_config(accid, key)
        return f"ok: {key}={result!r}"
    except Exception as exc:
        log.exception("Config error for key %r: %s", key, exc)
        return f"error: config error: {exc}"


def _socket_dispatch(line: str, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> str:
    """Parse and dispatch a single socket line by its first word (command)."""
    cmd, _, args = line.partition(" ")
    args = args.strip()
    if cmd == "alert":
        return _socket_do_alert(args, accid, rpc, alert_map)
    elif cmd == "status":
        return _socket_do_status(args, accid, rpc, status_map)
    elif cmd == "config":
        return _socket_do_config(args, accid, rpc)
    else:
        return f"error: unknown command {cmd!r}"


def _handle_client(conn: socket.socket, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> None:
    """Handle a single client connection, buffering input by newline."""
    buffer = ""
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buffer += data.decode()
            # Process all complete lines (ending with \n)
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                if line == "quit":
                    conn.sendall(b"ok: goodbye\n")
                    return
                try:
                    response = _socket_dispatch(line, accid, rpc, status_map, alert_map)
                    conn.sendall((response + "\n").encode())
                except Exception as exc:
                    log.exception("Error handling socket line %r: %s", line, exc)
                    conn.sendall(b"error: internal error\n")
    except Exception as exc:
        log.debug("Client connection error: %s", exc)
    finally:
        conn.close()


def _socket_listener_inet(host: str, port: int, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> None:
    """Blocking loop that accepts inet socket connections and handles clients."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    log.info("Socket listener started on %s:%d (inet)", host, port)

    try:
        while True:
            try:
                conn, addr = sock.accept()
                log.debug("Accepted connection from %s:%d", addr[0], addr[1])
                threading.Thread(
                    target=_handle_client,
                    args=(conn, accid, rpc, status_map, alert_map),
                    daemon=True,
                ).start()
            except Exception as exc:
                log.exception("Error accepting connection: %s", exc)
    finally:
        sock.close()


def _socket_listener_unix(path: str, accid: int, rpc: Rpc, status_map: dict, alert_map: dict) -> None:
    """Blocking loop that accepts unix socket connections and handles clients."""
    _ensure_unix_socket(path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    sock.listen(5)
    log.info("Socket listener started on %s (unix)", path)

    try:
        while True:
            try:
                conn, _ = sock.accept()
                threading.Thread(
                    target=_handle_client,
                    args=(conn, accid, rpc, status_map, alert_map),
                    daemon=True,
                ).start()
            except Exception as exc:
                log.exception("Error accepting connection: %s", exc)
    finally:
        sock.close()
        if os.path.exists(path):
            os.remove(path)


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
        "  /help   – show this\n"
        "  /ping   – check I'm alive\n"
        "  /alert  – manage alert chat (admin only)\n"
        "  /admin  – manage admin chat (admin only)\n"
        "  /chats  – list managed chats (admin only)\n"
        "  /leave  – leave a chat (admin only)"
    )
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=help_text))


def _on_ping(bot: Bot, accid: int, event) -> None:
    bot.rpc.send_msg(accid, event.msg.chat_id, MsgData(text="Pong! 🏓"))


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

    lines = ["Managed chats:"]
    if admin_chats:
        lines.append("Admin:")
        for cid in admin_chats:
            lines.append(f"  {cid}")
    if alert_chats:
        lines.append("Alert:")
        for cid in alert_chats:
            lines.append(f"  {cid}")
    if not admin_chats and not alert_chats:
        lines.append("(none)")

    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="\n".join(lines)))


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


def run_bot(
    rpc: Rpc,
    accid: int,
    listen_socket: str,
    listen_addr: str,
    heartbeat_interval: int,
    alert_dir: str = "",
    alert_interval: int = 60,
    status_dir: str = "",
    status_interval: int = 60,
) -> None:
    """Full implementation: message handlers + optional socket listeners + heartbeat."""
    addrs = get_addrs(rpc, accid)
    our_addr = addrs[0] if addrs else ""
    log.info("Listening at: %s", ", ".join(addrs))

    hb_state = _heartbeat.HeartbeatState(interval=heartbeat_interval)

    hooks = [
        (_on_new_message, events.NewMessage(is_bot=None)),
        (_on_help, events.NewMessage(command="/help")),
        (_on_ping, events.NewMessage(command="/ping")),
        (_on_alert, events.NewMessage(command="/alert")),
        (_on_admin, events.NewMessage(command="/admin")),
        (_on_chats, events.NewMessage(command="/chats")),
        (_on_leave, events.NewMessage(command="/leave")),
        (hb_state.make_handler(), events.NewMessage(is_bot=None)),
    ]
    bot = Bot(rpc, hooks, logger=log)

    status_map: dict[str, str] = {}
    alert_map: dict[str, str] = {}

    if listen_socket:
        threading.Thread(
            target=_socket_listener_unix,
            args=(listen_socket, accid, rpc, status_map, alert_map),
            name="socket-unix",
            daemon=True,
        ).start()

    if listen_addr:
        host, port_str = listen_addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            raise ValueError(f"Invalid inet socket address: {listen_addr}, expected host:port")
        threading.Thread(
            target=_socket_listener_inet,
            args=(host, port, accid, rpc, status_map, alert_map),
            name="socket-inet",
            daemon=True,
        ).start()

    if _bot._get_heartbeat_chats(rpc, accid):
        hb_state.start(rpc, accid, our_addr)

    # Send startup message to alert chats
    chat_ids = _bot._get_alert_chats(rpc, accid)
    if chat_ids:
        bot_name = rpc.get_config(accid, "displayname") or APP_NAME
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
