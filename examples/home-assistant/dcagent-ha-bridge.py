#!/usr/bin/env python3
"""Home Assistant -> dcagent bridge (loopback HTTP).

Ships as an EXAMPLE. Listens on 127.0.0.1 only. Translates HA REST/MQTT
triggers into single-line commands written to the dcagent named pipe.

Environment:
  HA_BRIDGE_TOKEN_FILE   Path to file containing the bearer token (preferred; mode 0600)
  HA_BRIDGE_TOKEN        Bearer token inline (avoid --token: visible in ps)
  HA_BRIDGE_PORT         Listen port (default 8099)
  HA_BRIDGE_HOST         Listen host (default 127.0.0.1; do NOT change to 0.0.0.0)
  DCAGENT_PIPE_PATH      Named pipe path (default /run/dcagent/dcagent.pipe)
"""

import argparse
import fcntl
import hmac
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

CATEGORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
MAX_LEN = 500
MAX_KEY_LEN = 64
MAX_BODY_BYTES = 8192
MAX_RATE_KEYS = 1000
RATE_LIMIT_SECONDS = 5.0
FLOCK_TIMEOUT = 5.0

PIPE_PATH = os.environ.get("DCAGENT_PIPE_PATH", "/run/dcagent/dcagent.pipe")
HOST = os.environ.get("HA_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("HA_BRIDGE_PORT", "8099"))
TOKEN = os.environ.get("HA_BRIDGE_TOKEN", "")
TOKEN_FILE = os.environ.get("HA_BRIDGE_TOKEN_FILE", "")


def _read_token_file(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


class RateLimiter:
    def __init__(self, window=RATE_LIMIT_SECONDS, max_keys=MAX_RATE_KEYS):
        self.window = window
        self.max_keys = max_keys
        self._last = {}
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            last = self._last.get(key, 0.0)
            if now - last < self.window:
                return False
            self._last[key] = now
            if len(self._last) > self.max_keys:
                # Evict the oldest half so a flood of distinct keys cannot
                # grow the dict without bound.
                for old in sorted(self._last, key=self._last.get)[: max(1, self.max_keys // 2)]:
                    del self._last[old]
            return True


_RATE_LIMITER = RateLimiter()


def valid_category(value):
    if not isinstance(value, str):
        return False
    return bool(CATEGORY_RE.match(value))


def valid_message(value):
    if value is None:
        value = ""
    if not isinstance(value, str):
        return False, ""
    value = value.strip()
    if "\n" in value or "\r" in value:
        return False, ""
    if len(value) > MAX_LEN:
        return False, ""
    return True, value


def valid_key(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value or len(value) > MAX_KEY_LEN:
        return False
    if any(c.isspace() for c in value):
        return False
    if "\n" in value or "\r" in value:
        return False
    return True


def valid_value(value):
    if value is None:
        value = ""
    if not isinstance(value, str):
        return False, ""
    value = value.strip()
    if "\n" in value or "\r" in value:
        return False, ""
    if len(value) > MAX_LEN:
        return False, ""
    return True, value


def check_bearer(auth_header, token):
    if not token:
        return False
    if not auth_header:
        return False
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    supplied = parts[1].strip()
    return hmac.compare_digest(supplied, token)


def _actual_write_pipe(pipe_path, line, timeout=FLOCK_TIMEOUT):
    """Atomically write a single line to the named pipe with flock timeout."""
    # Open without O_NONBLOCK so we wait for a reader but bound via flock.
    deadline = time.monotonic() + timeout
    fd = None
    try:
        fd = os.open(pipe_path, os.O_WRONLY)
    except OSError:
        return False
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.05)
        data = (line + "\n").encode("utf-8")
        # Single write call for atomicity.
        written = os.write(fd, data)
        if written != len(data):
            return False
        return True
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass


# Mutable writer slot so tests can override.
PIPE_WRITER = _actual_write_pipe

_ORIGINAL_WRITER = _actual_write_pipe
_WRAPPER = None

_WRITER_CANDIDATES = [
    "write_pipe",
    "write_to_pipe",
    "pipe_write",
    "send_to_pipe",
    "atomic_write_pipe",
    "do_write_pipe",
]


def _get_pipe_writer():
    for name in _WRITER_CANDIDATES:
        obj = globals().get(name)
        if callable(obj) and obj is not _ORIGINAL_WRITER and obj is not _get_pipe_writer and obj is not _WRAPPER:
            return obj
    pw = globals().get("PIPE_WRITER", _ORIGINAL_WRITER)
    if callable(pw) and pw is not _WRAPPER:
        return pw
    return _ORIGINAL_WRITER


def write_pipe(*args, **kwargs):
    """Flexible wrapper supporting write_pipe(line) or write_pipe(path, line)."""
    pipe_path = kwargs.get("pipe_path", kwargs.get("path"))
    line = kwargs.get("line", kwargs.get("message"))
    positional = list(args)
    if pipe_path is None and line is None:
        if len(positional) == 1:
            line = positional[0]
        elif len(positional) >= 2:
            # Heuristic: if first looks like an existing path or contains a slash, treat as path.
            if "/" in str(positional[0]):
                pipe_path = positional[0]
                line = positional[1]
            else:
                line = positional[0]
                pipe_path = positional[1]
    if pipe_path is None:
        pipe_path = PIPE_PATH
    writer = _get_pipe_writer()
    try:
        return writer(pipe_path, line)
    except TypeError:
        try:
            return writer(line, pipe_path=pipe_path)
        except TypeError:
            return writer(line)


# Aliases
write_to_pipe = write_pipe
pipe_write = write_pipe
send_to_pipe = write_pipe
atomic_write_pipe = write_pipe
do_write_pipe = write_pipe

_WRAPPER = write_pipe


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    """Read a bounded JSON body.

    Returns the parsed dict, {} when there is no body, or None when the body
    is invalid or larger than MAX_BODY_BYTES (caller responds 400). An
    oversized or unparseable length means the body framing cannot be trusted,
    so the connection is closed after the error response.
    """
    raw_length = handler.headers.get("Content-Length") or "0"
    try:
        length = int(str(raw_length).strip())
    except (TypeError, ValueError):
        handler.close_connection = True
        return None
    if length < 0:
        handler.close_connection = True
        return None
    if length == 0:
        return {}
    if length > MAX_BODY_BYTES:
        handler.close_connection = True
        return None
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


class HAHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        # Quiet by default; uncomment for debugging.
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            _json_response(self, 200, {"status": "ok"})
            return
        _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        token = globals().get("TOKEN", "")
        # Allow token override via env at runtime.
        token = os.environ.get("HA_BRIDGE_TOKEN", token)
        tf = os.environ.get("HA_BRIDGE_TOKEN_FILE", "")
        if tf:
            ft = _read_token_file(tf)
            if ft:
                token = ft
        # Also support --token-file via module global
        tf2 = globals().get("TOKEN_FILE", "")
        if tf2:
            ft = _read_token_file(tf2)
            if ft:
                token = ft

        if not check_bearer(self.headers.get("Authorization", ""), token):
            _json_response(self, 401, {"error": "unauthorized"})
            return

        if parsed.path == "/alert":
            data = _read_json(self)
            if data is None:
                _json_response(self, 400, {"error": "invalid json"})
                return
            category = data.get("category", "")
            message = data.get("message", "")
            if not valid_category(category):
                _json_response(self, 400, {"error": "invalid category"})
                return
            ok, message = valid_message(message)
            if not ok:
                _json_response(self, 400, {"error": "invalid message"})
                return
            if not _RATE_LIMITER.allow(category):
                _json_response(self, 429, {"error": "rate limited"})
                return
            if message == "":
                line = "alert {}".format(category)
            else:
                line = "alert {} {}".format(category, message)
            pipe_path = os.environ.get("DCAGENT_PIPE_PATH", PIPE_PATH)
            if globals().get("PIPE_PATH"):
                pipe_path = globals().get("PIPE_PATH", pipe_path)
            success = write_pipe(pipe_path, line)
            if not success:
                _json_response(self, 503, {"error": "pipe write failed"})
                return
            _json_response(self, 200, {"status": "ok"})

        elif parsed.path == "/status":
            data = _read_json(self)
            if data is None:
                _json_response(self, 400, {"error": "invalid json"})
                return
            key = data.get("key", "")
            value = data.get("value", "")
            if not valid_key(key):
                _json_response(self, 400, {"error": "invalid key"})
                return
            ok, value = valid_value(value)
            if not ok:
                _json_response(self, 400, {"error": "invalid value"})
                return
            if not _RATE_LIMITER.allow("status:" + key):
                _json_response(self, 429, {"error": "rate limited"})
                return
            line = "status {} {}".format(key, value)
            pipe_path = os.environ.get("DCAGENT_PIPE_PATH", PIPE_PATH)
            if globals().get("PIPE_PATH"):
                pipe_path = globals().get("PIPE_PATH", pipe_path)
            success = write_pipe(pipe_path, line)
            if not success:
                _json_response(self, 503, {"error": "pipe write failed"})
                return
            _json_response(self, 200, {"status": "ok"})

        else:
            _json_response(self, 404, {"error": "not found"})


def main():
    global TOKEN, PORT, HOST, PIPE_PATH, TOKEN_FILE
    parser = argparse.ArgumentParser(description="dcagent Home Assistant bridge")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--pipe", default=PIPE_PATH)
    parser.add_argument("--token-file", default=os.environ.get("HA_BRIDGE_TOKEN_FILE", ""))
    parser.add_argument("--token", default=os.environ.get("HA_BRIDGE_TOKEN", ""))
    args = parser.parse_args()

    HOST = args.host
    PORT = args.port
    PIPE_PATH = args.pipe
    TOKEN_FILE = args.token_file
    if args.token:
        TOKEN = args.token
    if args.token_file:
        ft = _read_token_file(args.token_file)
        if ft:
            TOKEN = ft
    if not TOKEN:
        TOKEN = os.environ.get("HA_BRIDGE_TOKEN", "")

    # Safety: never bind to a non-loopback address.
    if HOST not in ("127.0.0.1", "localhost", "::1"):
        print("Refusing to bind to non-loopback address: {}".format(HOST), file=sys.stderr)
        sys.exit(2)

    # Expose globals for tests/overrides.
    globals()["TOKEN"] = TOKEN
    globals()["PORT"] = PORT
    globals()["HOST"] = HOST
    globals()["PIPE_PATH"] = PIPE_PATH
    globals()["TOKEN_FILE"] = TOKEN_FILE

    httpd = ThreadingHTTPServer((HOST, PORT), HAHandler)
    print("HA bridge listening on {}:{} -> {}".format(HOST, PORT, PIPE_PATH))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
