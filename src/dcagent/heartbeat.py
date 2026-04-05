"""
dcagent heartbeat — liveness monitoring protocol.

Each node periodically broadcasts a heartbeat message to the shared heartbeat
group chat. If a node goes silent beyond the timeout, the elected master node
forwards an alert to the alert channel.

See docs/heartbeat.md for the full protocol specification.
"""

import logging
import os
import threading
import time

from deltachat2 import Bot, MsgData, Rpc

import dcagent.bot as _bot

log = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "60"))
_HEARTBEAT_TIMEOUT = HEARTBEAT_INTERVAL * 3
_MASTER_WINDOW = HEARTBEAT_INTERVAL * 2


class HeartbeatState:
    """Shared mutable state between the sender thread and the message handler."""

    def __init__(self) -> None:
        self.seq: int = 0
        self.last_seen: dict[str, float] = {}  # addr -> monotonic timestamp
        self.offline: set[str] = set()
        self.lock = threading.Lock()


def _is_master(our_addr: str, last_seen: dict[str, float], now: float) -> bool:
    """Return True if we are the elected master (smallest addr among alive nodes)."""
    alive = {addr for addr, ts in last_seen.items() if now - ts <= _MASTER_WINDOW}
    alive.add(our_addr)
    return our_addr == min(alive)


def sender_thread(rpc: Rpc, accid: int, our_addr: str, state: HeartbeatState) -> None:
    """Periodically broadcast a heartbeat and check for offline/recovered nodes."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)

        # Send our heartbeat to all heartbeat chats.
        with state.lock:
            state.seq += 1
            seq = state.seq

        text = f"heartbeat {our_addr} {seq}"
        for chat_id in _bot._get_heartbeat_chats(rpc, accid):
            try:
                rpc.send_msg(accid, chat_id, MsgData(text=text))
                log.debug("Sent heartbeat seq=%d to chat %d", seq, chat_id)
            except Exception as exc:
                log.warning("Failed to send heartbeat to chat %d: %s", chat_id, exc)

        # Snapshot state for offline/recovery checks.
        now = time.monotonic()
        with state.lock:
            last_seen = dict(state.last_seen)
            offline_snap = set(state.offline)

        is_master = _is_master(our_addr, last_seen, now)

        newly_offline = [
            (addr, now - ts)
            for addr, ts in last_seen.items()
            if now - ts > _HEARTBEAT_TIMEOUT and addr not in offline_snap
        ]
        newly_recovered = [
            addr for addr in offline_snap if addr in last_seen and now - last_seen[addr] <= _HEARTBEAT_TIMEOUT
        ]

        with state.lock:
            state.offline.update(addr for addr, _ in newly_offline)
            state.offline -= set(newly_recovered)

        if is_master:
            for addr, elapsed in newly_offline:
                mins = int(elapsed / 60)
                log.warning("Heartbeat: node offline: %s (last seen %dm ago)", addr, mins)
                _forward_alert(f"⚠️ Node offline: {addr} (last seen {mins}m ago)", accid, rpc)
            for addr in newly_recovered:
                log.info("Heartbeat: node recovered: %s", addr)
                _forward_alert(f"✅ Node recovered: {addr}", accid, rpc)


def make_handler(state: HeartbeatState):
    """Return a NewMessage handler that records incoming heartbeats."""

    def _on_heartbeat(bot: Bot, accid: int, event) -> None:
        msg = event.msg
        if msg.chat_id not in _bot._get_heartbeat_chats(bot.rpc, accid):
            return
        parts = (msg.text or "").split()
        if len(parts) < 3 or parts[0] != "heartbeat":
            return
        addr = parts[1]
        with state.lock:
            state.last_seen[addr] = time.monotonic()
        log.debug("Heartbeat received from %s seq=%s", addr, parts[2])

    return _on_heartbeat


def _forward_alert(text: str, accid: int, rpc: Rpc) -> None:
    chat_ids = _bot._get_alert_chats(rpc, accid)
    if not chat_ids:
        log.warning("Heartbeat alert but no alert chats configured: %s", text)
        return
    for chat_id in chat_ids:
        log.info("Heartbeat alert to chat %d: %r", chat_id, text[:80])
        rpc.send_msg(accid, chat_id, MsgData(text=text))


def start(rpc: Rpc, accid: int, our_addr: str, state: HeartbeatState) -> None:
    """Start the heartbeat sender thread."""
    t = threading.Thread(
        target=sender_thread,
        args=(rpc, accid, our_addr, state),
        name="heartbeat",
        daemon=True,
    )
    t.start()
    log.info("Heartbeat started (interval=%ds, timeout=%ds)", HEARTBEAT_INTERVAL, _HEARTBEAT_TIMEOUT)
