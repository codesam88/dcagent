"""
dcagent heartbeat — liveness monitoring protocol.

Each node periodically broadcasts a heartbeat message to the shared heartbeat
group chat. If a node goes silent beyond the timeout, the elected master node
forwards an alert to the alert channel.

See docs/heartbeat.md for the full protocol specification.
"""

import logging
import threading
import time

from deltachat2 import Bot, MsgData, Rpc

import dcagent.bot as _bot

log = logging.getLogger(__name__)


class HeartbeatState:
    """Heartbeat protocol state, sender thread, and message handler."""

    def __init__(self, interval: int = 60) -> None:
        self.interval: int = interval
        self.timeout: int = interval * 3
        self.master_window: int = interval * 2
        self.seq: int = 0
        self.last_seen: dict[str, float] = {}  # addr -> monotonic timestamp
        self.offline: set[str] = set()
        self.lock = threading.Lock()
        self._started: bool = False

    def _next_seq(self) -> int:
        with self.lock:
            self.seq = self.seq + 1 % 1000
            return self.seq

    def _read_state(self) -> tuple[dict, set]:
        with self.lock:
            return dict(self.last_seen), set(self.offline)

    def _apply_status(self, newly_offline: list, newly_recovered: list) -> None:
        with self.lock:
            self.offline.update(addr for addr, _ in newly_offline)
            self.offline -= set(newly_recovered)

    def _mark_seen(self, addr: str) -> None:
        with self.lock:
            self.last_seen[addr] = time.monotonic()

    def _is_master(self, our_addr: str, last_seen: dict[str, float], offline: set[str], now: float) -> bool:
        """Return True if we are the elected master (smallest addr among alive nodes).

        Nodes currently tracked as offline are excluded from the election so that
        a recovering node cannot immediately displace the master that is handling
        its offline/recovery lifecycle.
        """
        alive = {addr for addr, ts in last_seen.items() if now - ts <= self.master_window and addr not in offline}
        alive.add(our_addr)
        return our_addr == min(alive)

    def _forward_alert(self, text: str, accid: int, rpc: Rpc) -> None:
        chat_ids = _bot._get_alert_chats(rpc, accid)
        if not chat_ids:
            log.warning("Heartbeat alert but no alert chats configured: %s", text)
            return
        for chat_id in chat_ids:
            log.info("Heartbeat alert to chat %d: %r", chat_id, text[:80])
            rpc.send_msg(accid, chat_id, MsgData(text=text))

    def sender_thread(self, rpc: Rpc, accid: int, our_addr: str) -> None:
        """Periodically broadcast a heartbeat and check for offline/recovered nodes."""
        while True:
            time.sleep(self.interval)

            seq = self._next_seq()
            text = f"tick {our_addr} {seq}"
            for chat_id in _bot._get_heartbeat_chats(rpc, accid):
                try:
                    rpc.send_msg(accid, chat_id, MsgData(text=text))
                    log.debug("Sent tick seq=%d to chat %d", seq, chat_id)
                except Exception as exc:
                    log.warning("Failed to send heartbeat to chat %d: %s", chat_id, exc)

            now = time.monotonic()
            last_seen, offline_snap = self._read_state()
            # Offline nodes are excluded from master election so that a recovering
            # node cannot immediately displace the master mid-lifecycle.
            is_master = self._is_master(our_addr, last_seen, offline_snap, now)

            newly_offline = [
                (addr, now - ts)
                for addr, ts in last_seen.items()
                if now - ts > self.timeout and addr not in offline_snap
            ]
            newly_recovered = [
                addr for addr in offline_snap if addr in last_seen and now - last_seen[addr] <= self.timeout
            ]

            self._apply_status(newly_offline, newly_recovered)

            if is_master:
                for addr, elapsed in newly_offline:
                    mins = int(elapsed / 60)
                    log.warning("Heartbeat: node offline: %s (last seen %dm ago)", addr, mins)
                    self._forward_alert(f"⚠️ Node offline: {addr} (last seen {mins}m ago)", accid, rpc)
                for addr in newly_recovered:
                    log.info("Heartbeat: node recovered: %s", addr)
                    self._forward_alert(f"✅ Node recovered: {addr}", accid, rpc)

    def make_handler(self):
        """Return a NewMessage handler that records incoming heartbeats."""

        def _on_heartbeat(bot: Bot, accid: int, event) -> None:
            msg = event.msg
            if msg.chat_id not in _bot._get_heartbeat_chats(bot.rpc, accid):
                return
            parts = (msg.text or "").split()
            if len(parts) < 3 or parts[0] != "tick":
                return
            addr = parts[1]
            self._mark_seen(addr)
            log.debug("Tick received from %s seq=%s", addr, parts[2])

        return _on_heartbeat

    def start(self, rpc: Rpc, accid: int, our_addr: str) -> None:
        """Start the heartbeat sender thread. Idempotent — safe to call multiple times."""
        with self.lock:
            if self._started:
                return
            self._started = True
        t = threading.Thread(
            target=self.sender_thread,
            args=(rpc, accid, our_addr),
            name="heartbeat",
            daemon=True,
        )
        t.start()
        log.info("Heartbeat started (interval=%ds, timeout=%ds)", self.interval, self.timeout)
