"""
dcagent bot — lifecycle commands, RPC infrastructure, and CLI entry point.

Provides the do_* lifecycle commands (init, config, alert, admin, serve),
shared helpers, and main(). run_bot() has a minimal default implementation
that agent.py overrides with the full handler/socket stack.

Usage:
    dcagent [--account-db PATH] [--log-level LEVEL] [--log-file PATH] <subcommand> [args]

Subcommands:
    init ADDR [PASSWORD]   – configure a new account
    config [KEY [VALUE]]   – get/set account configuration
    alert [INVITE]        – print alert-group invite link, or join one via SecureJoin
    heartbeat [INVITE]     – print heartbeat-group invite link, or join one via SecureJoin
    admin [INVITE]         – print admin-group invite link, or join one via SecureJoin
    status                 – print account status and alert/admin invite links
    serve [--listen-socket PATH] [--listen-addr ADDR]    – run the bot (event loop + optional socket listeners)

Socket input format:
    <command> [args...]

    alert <category> [message]   update alert state; only sends if state changed or category=""
    status <key> <msg>           update status element key to msg
"""

import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from argparse import ArgumentParser, Namespace
from typing import Optional

from appdirs import user_config_dir
from deltachat2 import Bot, CoreEvent, EventType, IOTransport, JsonRpcError, Rpc

APP_NAME = "dcagent"
_JOIN_TIMEOUT = 60
_INIT_TIMEOUT = 120

log = logging.getLogger(__name__)

# Track the current account database for lock cleanup
_LOCKED_ACCOUNT_DB: Optional[str] = None


def _atexit_cleanup() -> None:
    """Clean up lock file on exit."""
    global _LOCKED_ACCOUNT_DB
    if _LOCKED_ACCOUNT_DB:
        _remove_dcagent_lock(_LOCKED_ACCOUNT_DB)
        _LOCKED_ACCOUNT_DB = None


def _signal_handler(signum: int, frame) -> None:
    """Handle termination signals by exiting cleanly (atexit will clean up)."""
    sys.exit(0)


# Register handlers
atexit.register(_atexit_cleanup)
signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


def _get_version() -> str:
    try:
        from importlib.metadata import version

        return version("dcagent")
    except Exception:
        return "unknown"


class AgentError(Exception):
    """Fatal user-facing error — logged and exits with code 1."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _accounts_dir(config_dir: str) -> str:
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "accounts")


def _get_dcagent_lock_file(account_db: str) -> str:
    """Get path to dcagent's own lock file for this account."""
    accounts_dir = _accounts_dir(account_db)
    return os.path.join(accounts_dir, ".dcagent.lock")


def _check_dcagent_lock(account_db: str) -> Optional[str]:
    """Check if another dcagent process holds a lock.

    Retries a few times to allow cleanup from recently terminated processes.
    Returns lock file path if it exists after retries, None otherwise.
    """
    for attempt in range(5):
        lock_file = _get_dcagent_lock_file(account_db)
        if not os.path.exists(lock_file):
            return None
        if attempt < 4:  # Don't sleep on last attempt
            time.sleep(0.5)
    return lock_file


def _write_dcagent_lock(account_db: str) -> None:
    """Write lock file with current process PID."""
    lock_file = _get_dcagent_lock_file(account_db)
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass  # Lock file write failure is not fatal


def _remove_dcagent_lock(account_db: str) -> None:
    """Remove lock file."""
    lock_file = _get_dcagent_lock_file(account_db)
    try:
        os.remove(lock_file)
    except OSError:
        pass  # Lock file removal failure is not fatal


def _get_account(rpc: Rpc) -> int:
    accounts = rpc.get_all_account_ids()
    if not accounts:
        raise AgentError("No accounts configured. Run 'init' first.")
    return accounts[0]


def _ensure_configured(rpc: Rpc, accid: int) -> None:
    if not rpc.is_configured(accid):
        raise AgentError("Account not configured. Run 'init' first.")


def get_addrs(rpc: Rpc, accid: int) -> list:
    return [p["addr"] for p in rpc.list_transports(accid)]


def _get_or_create_admin_chat(rpc: Rpc, accid: int) -> int:
    """Return the first admin chat, creating a new group if none exist."""
    chats = _get_admin_chats(rpc, accid)
    if chats:
        return chats[0]
    displayname = rpc.get_config(accid, "displayname") or "Bot"
    chatid = rpc.create_group_chat(accid, f"{displayname} admins", True)
    _add_admin_chat(rpc, accid, chatid)
    return chatid


def _get_admin_chats(rpc: Rpc, accid: int) -> list[int]:
    raw = rpc.get_config(accid, "ui.admin_chats") or ""
    return [int(x) for x in raw.split(",") if x.strip()]


def _add_admin_chat(rpc: Rpc, accid: int, chat_id: int) -> None:
    chats = _get_admin_chats(rpc, accid)
    if chat_id not in chats:
        chats.append(chat_id)
    rpc.set_config(accid, "ui.admin_chats", ",".join(str(c) for c in chats))


def _get_alert_chats(rpc: Rpc, accid: int) -> list[int]:
    raw = rpc.get_config(accid, "ui.alert_chats") or ""
    return [int(x) for x in raw.split(",") if x.strip()]


def _add_alert_chat(rpc: Rpc, accid: int, chat_id: int) -> None:
    chats = _get_alert_chats(rpc, accid)
    if chat_id not in chats:
        chats.append(chat_id)
    rpc.set_config(accid, "ui.alert_chats", ",".join(str(c) for c in chats))


def _get_or_create_alert_chat(rpc: Rpc, accid: int) -> int:
    """Return the first alert chat, creating a new group if none exist."""
    chats = _get_alert_chats(rpc, accid)
    if chats:
        return chats[0]
    displayname = rpc.get_config(accid, "displayname") or "Bot"
    chatid = rpc.create_group_chat(accid, f"{displayname} alerts", True)
    _add_alert_chat(rpc, accid, chatid)
    return chatid


def _get_heartbeat_chats(rpc: Rpc, accid: int) -> list[int]:
    raw = rpc.get_config(accid, "ui.heartbeat_chats") or ""
    return [int(x) for x in raw.split(",") if x.strip()]


def _add_heartbeat_chat(rpc: Rpc, accid: int, chat_id: int) -> None:
    chats = _get_heartbeat_chats(rpc, accid)
    if chat_id not in chats:
        chats.append(chat_id)
    rpc.set_config(accid, "ui.heartbeat_chats", ",".join(str(c) for c in chats))


def _get_or_create_heartbeat_chat(rpc: Rpc, accid: int) -> int:
    """Return the first heartbeat chat, creating a new group if none exist."""
    chats = _get_heartbeat_chats(rpc, accid)
    if chats:
        return chats[0]
    displayname = rpc.get_config(accid, "displayname") or "Bot"
    chatid = rpc.create_group_chat(accid, f"{displayname} heartbeat", True)
    _add_heartbeat_chat(rpc, accid, chatid)
    return chatid


def _securejoin(rpc: Rpc, accid: int, invite: str) -> int:
    """Perform a SecureJoin handshake and return the resulting chat ID."""
    rpc.start_io(accid)
    chat_id = rpc.secure_join(accid, invite)
    log.info("SecureJoin initiated (chat_id=%s), waiting for handshake…", chat_id)

    deadline = time.monotonic() + _JOIN_TIMEOUT
    while time.monotonic() < deadline:
        raw = rpc.get_next_event()
        ev = CoreEvent(raw.event)
        if ev.kind == EventType.SECUREJOIN_JOINER_PROGRESS:
            log.debug("SecureJoin progress: %d%%", ev.progress // 10)
            if ev.progress == 1000:
                return chat_id
            if ev.progress == 0:
                raise AgentError("SecureJoin failed or was cancelled")
    raise AgentError(f"SecureJoin timed out after {_JOIN_TIMEOUT}s")


# ---------------------------------------------------------------------------
# Lifecycle commands
# ---------------------------------------------------------------------------


def do_init(rpc: Rpc, args: Namespace) -> None:
    """Configure a new account (there can be only one)."""
    accounts = rpc.get_all_account_ids()
    if not accounts:
        accid = rpc.add_account()
    else:
        if args.force:
            rpc.remove_account(accounts[0])
            accid = rpc.add_account()
        else:
            raise AgentError("Account is already initialized. Use init --force to re-initialize.")

    rpc.set_config(accid, "bot", "1")
    log.info("Configuring account #%d ...", accid)

    done = threading.Event()
    failed: list[str] = []

    def _watch_configure() -> None:
        while True:
            raw = rpc.get_next_event()
            ev = CoreEvent(raw.event)
            if ev.kind == EventType.CONFIGURE_PROGRESS:
                if ev.comment:
                    log.debug("%s", ev.comment)
                if ev.progress == 1000:
                    done.set()
                    break
                if ev.progress == 0:
                    failed.append(ev.comment or "Configuration failed")
                    done.set()
                    break

    t = threading.Thread(target=_watch_configure, daemon=True)
    t.start()

    try:
        if not args.password:
            rpc.add_transport_from_qr(accid, args.addr)
        else:
            rpc.add_or_update_transport(accid, {"addr": args.addr, "password": args.password})
    except JsonRpcError as exc:
        raise AgentError(f"Configuration error: {exc}") from exc

    t.join(timeout=_INIT_TIMEOUT)
    if t.is_alive():
        raise AgentError(f"Configuration timed out after {_INIT_TIMEOUT}s")

    if failed:
        raise AgentError(failed[0])

    addrs = get_addrs(rpc, accid)
    log.info("Account #%d configured: %s", accid, ", ".join(addrs))


def _get_config_output(rpc: Rpc, accid: int, key: str | None = None, value: str | None = None) -> list[str]:
    """Shared implementation for config command.

    Returns list of output lines for displaying/getting/setting configuration.
    When key is None, dumps all config keys. When key is provided, gets/sets that key.
    """
    output = []

    if key:
        # Get or set specific key
        if value is not None:
            rpc.set_config(accid, key, value)
        result = rpc.get_config(accid, key)
        output.append(f"{key}={result!r}")
    else:
        # Dump all config keys
        keys = rpc.get_config(accid, "sys.config_keys") or ""
        for k in keys.split():
            v = rpc.get_config(accid, k)
            output.append(f"{k}={v!r}")

    return output


def do_config(rpc: Rpc, args: Namespace) -> None:
    """Get or set account configuration values."""
    accid = _get_account(rpc)

    try:
        lines = _get_config_output(rpc, accid, key=args.key, value=args.value)
        for line in lines:
            print(line)
    except JsonRpcError as exc:
        raise AgentError(f"Unknown configuration key: {args.key}") from exc


def do_alert(rpc: Rpc, args: Namespace) -> None:
    """Print the alert-group invite link, or join a chat and add it to the alert group.

    Without an invite argument: prints the SecureJoin invite link for this bot's
    alert group, creating the group first if it doesn't exist. Anyone who joins
    will receive pipe messages.

    With an invite argument: joins the chat via SecureJoin and registers it in
    the alert group (ui.alert_chats). The pipe listener will send messages to
    all chats in this group.
    """
    accid = _get_account(rpc)
    _ensure_configured(rpc, accid)

    if not args.invite:
        chatid = _get_or_create_alert_chat(rpc, accid)
        print(rpc.get_chat_securejoin_qr_code(accid, chatid))
        return

    chat_id = _securejoin(rpc, accid, args.invite)
    _add_alert_chat(rpc, accid, chat_id)
    log.info("Joined alert chat (chat_id=%s)", chat_id)


def do_heartbeat(rpc: Rpc, args: Namespace) -> None:
    """Print the heartbeat-group invite link, or join one via SecureJoin.

    Without an invite argument: prints the invite link for this bot's heartbeat
    group, creating the group first if it doesn't exist.

    With an invite argument: joins the chat via SecureJoin and registers it as
    the heartbeat chat (ui.heartbeat_chats).
    """
    accid = _get_account(rpc)
    _ensure_configured(rpc, accid)

    if not args.invite:
        chatid = _get_or_create_heartbeat_chat(rpc, accid)
        print(rpc.get_chat_securejoin_qr_code(accid, chatid))
        return

    chat_id = _securejoin(rpc, accid, args.invite)
    _add_heartbeat_chat(rpc, accid, chat_id)
    log.info("Joined heartbeat chat (chat_id=%s)", chat_id)


def do_admin(rpc: Rpc, args: Namespace) -> None:
    """Print the admin-group invite link, or join an existing one via SecureJoin.

    Without an invite argument: prints the invite link for this bot's admin group
    (keep secret — anyone who joins becomes admin).

    With an invite argument: joins the admin channel identified by the SecureJoin
    invite link and stores it as this bot's admin chat.
    """
    accid = _get_account(rpc)
    _ensure_configured(rpc, accid)

    if not args.invite:
        chatid = _get_or_create_admin_chat(rpc, accid)
        print(rpc.get_chat_securejoin_qr_code(accid, chatid))
        return

    chat_id = _securejoin(rpc, accid, args.invite)
    _add_admin_chat(rpc, accid, chat_id)
    log.info("Joined admin channel (chat_id=%s)", chat_id)


def do_status(rpc: Rpc, args: Namespace) -> None:
    """Print account status"""
    print(f"dcagent {_get_version()}")
    accounts = rpc.get_all_account_ids()
    if not accounts:
        print("no accounts configured")
        return
    accid = accounts[0]
    configured = rpc.is_configured(accid)
    addr = rpc.get_config(accid, "addr") or "(no address)"
    displayname = rpc.get_config(accid, "displayname") or ""
    name_part = f" ({displayname})" if displayname else ""
    status = "configured" if configured else "not configured"
    print(f"Account #{accid}: {addr}{name_part} [{status}]")

    if not configured:
        return


def do_serve(rpc: Rpc, args: Namespace) -> None:
    """Start the bot event loop."""
    accid = _get_account(rpc)
    _ensure_configured(rpc, accid)

    run_bot(
        rpc,
        accid,
        args.listen_socket,
        args.listen_addr,
        args.heartbeat,
        args.alert_dir,
        args.alert_interval,
        args.status_dir,
        args.status_interval,
        args.testmode,
    )


# ---------------------------------------------------------------------------
# run_bot — default implementation (no handlers, no pipe).
# Override by assigning dcagent.bot.run_bot = your_function before main().
# agent.py does this automatically when imported.
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
    testmode: bool = False,
) -> None:
    """Minimal bot: bare event loop with no message handlers."""
    addrs = get_addrs(rpc, accid)
    log.info("Listening at: %s", ", ".join(addrs))
    bot = Bot(rpc, [], logger=log)
    while True:
        try:
            bot.run_forever(accid)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            log.exception("Event loop error: %s", exc)
            time.sleep(5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        APP_NAME,
        description=__doc__,
        formatter_class=lambda prog: __import__("argparse").RawDescriptionHelpFormatter(prog),
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {_get_version()}")
    parser.add_argument(
        "--account-db",
        "-c",
        metavar="PATH",
        default=os.environ.get("DCAGENT_ACCOUNT_DB", user_config_dir(APP_NAME)),
        help="account database folder (default: %(default)s, env: DCAGENT_ACCOUNT_DB)",
    )
    parser.add_argument(
        "--log-file",
        "-l",
        metavar="PATH",
        default=os.environ.get("DCAGENT_LOG_FILE"),
        help="also write logs to this file (env: DCAGENT_LOG_FILE)",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        default=os.environ.get("DCAGENT_LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error"],
        help="log level (default: %(default)s, env: DCAGENT_LOG_LEVEL)",
    )

    sub = parser.add_subparsers(title="subcommands", dest="subcommand")

    p = sub.add_parser("init", help="configure a new account")
    p.add_argument("--force", "-f", action="store_true", help="force init even if an account already exists")
    p.add_argument("addr", help="email address or DCACCOUNT URI (e.g. DCACCOUNT:https://nine.testrun.org/new)")
    p.add_argument("password", nargs="?", help="password (not needed for DCACCOUNT URIs)")

    p = sub.add_parser("config", help="get or set account attributes")
    p.add_argument("key", nargs="?", help="config key")
    p.add_argument("value", nargs="?", help="value to set")

    p = sub.add_parser("alert", help="print personal invite link, or join a chat and add it to the alert group")
    p.add_argument("invite", nargs="?", metavar="INVITE", help="if given, join this chat via SecureJoin")

    p = sub.add_parser("heartbeat", help="print heartbeat-group invite link, or join one via SecureJoin")
    p.add_argument("invite", nargs="?", metavar="INVITE", help="if given, join this chat via SecureJoin")

    p = sub.add_parser("admin", help="print admin-group invite link, or join one via SecureJoin")
    p.add_argument("invite", nargs="?", metavar="INVITE", help="if given, join this admin channel via SecureJoin")

    p = sub.add_parser("serve", help="run the bot")
    p.add_argument(
        "--listen-socket",
        metavar="PATH",
        default=os.environ.get("DCAGENT_LISTEN_SOCKET"),
        help="Unix domain socket path (env: DCAGENT_LISTEN_SOCKET)",
    )
    p.add_argument(
        "--listen-addr",
        metavar="ADDR",
        default=os.environ.get("DCAGENT_LISTEN_ADDR"),
        help="inet socket address host:port (env: DCAGENT_LISTEN_ADDR)",
    )
    p.add_argument(
        "--heartbeat",
        metavar="SECONDS",
        type=int,
        default=int(os.environ.get("DCAGENT_HEARTBEAT", "60")),
        help="heartbeat interval in seconds (default: %(default)s, env: DCAGENT_HEARTBEAT)",
    )
    p.add_argument(
        "--alert-dir",
        metavar="PATH",
        default=os.environ.get("DCAGENT_ALERT_DIR"),
        help="run run-parts on this directory for alert scripts (env: DCAGENT_ALERT_DIR)",
    )
    p.add_argument(
        "--alert-interval",
        metavar="SECONDS",
        type=int,
        default=int(os.environ.get("DCAGENT_ALERT_INTERVAL", "60")),
        help="how often to run alert scripts in seconds (default: %(default)s, env: DCAGENT_ALERT_INTERVAL)",
    )
    p.add_argument(
        "--status-dir",
        metavar="PATH",
        default=os.environ.get("DCAGENT_STATUS_DIR"),
        help="run run-parts on this directory for status scripts (env: DCAGENT_STATUS_DIR)",
    )
    p.add_argument(
        "--status-interval",
        metavar="SECONDS",
        type=int,
        default=int(os.environ.get("DCAGENT_STATUS_INTERVAL", "60")),
        help="how often to run status scripts in seconds (default: %(default)s, env: DCAGENT_STATUS_INTERVAL)",
    )
    p.add_argument(
        "--testmode",
        action="store_true",
        help="enable test mode with dcmsg socket command",
    )

    sub.add_parser("status", help="print bot/account status")

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if args.log_file:
        fh = logging.FileHandler(args.log_file)
        fh.setLevel(getattr(logging, args.log_level.upper()))
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logging.getLogger().addHandler(fh)

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    accounts_dir = _accounts_dir(args.account_db)
    kwargs = {} if args.log_level == "debug" else {"stderr": subprocess.DEVNULL}

    # Check if another process holds a lock
    lock_file = _check_dcagent_lock(args.account_db)
    if lock_file:
        log.error("Could not acquire lock. Another dcagent process is running this account.")
        log.error("Lock file: %s", lock_file)
        sys.exit(1)

    try:
        global _LOCKED_ACCOUNT_DB
        _write_dcagent_lock(args.account_db)
        _LOCKED_ACCOUNT_DB = args.account_db
        with IOTransport(accounts_dir=accounts_dir, **kwargs) as trans:
            rpc = Rpc(trans)
            log.debug("deltachat core %s", rpc.get_system_info().deltachat_core_version)
            dispatch = {
                "init": do_init,
                "config": do_config,
                "alert": do_alert,
                "heartbeat": do_heartbeat,
                "admin": do_admin,
                "serve": do_serve,
                "status": do_status,
            }
            dispatch[args.subcommand](rpc, args)
    except AgentError as exc:
        log.error("%s", exc)
        sys.exit(1)

    sys.exit(0)  # trigger atexit handler for final cleanup


if __name__ == "__main__":
    main()
