import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

BRIDGE_PATH = "examples/home-assistant/dcagent-ha-bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("dcagent_ha_bridge", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def bridge():
    return load_bridge()


@pytest.fixture
def server(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "TOKEN", "secret-token")
    monkeypatch.setattr(bridge, "TOKEN_FILE", "")
    monkeypatch.setattr(bridge, "_RATE_LIMITER", bridge.RateLimiter(window=0.0))
    from unittest.mock import MagicMock

    mw = MagicMock(return_value=True)
    monkeypatch.setattr(bridge, "write_pipe", mw)
    # ensure resolver sees mock
    bridge.write_pipe = mw
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), bridge.HAHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, mw, bridge
    httpd.shutdown()
    httpd.server_close()


def _req(base, path, method="GET", data=None, token="secret-token"):
    url = f"http://127.0.0.1:{base}{path}"
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    return _read_response(req)


def _post_raw(base, path, body, extra_headers=None):
    """POST a raw body (bypasses json encoding) for Content-Length edge cases."""
    url = f"http://127.0.0.1:{base}{path}"
    headers = {"Authorization": "Bearer secret-token", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return _read_response(req)


def _read_response(req):
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/health", token=None)
    assert status == 200
    assert body["status"] == "ok"


def test_auth_required(server):
    httpd, mw, bridge = server
    payload = {"category": "ha-test", "message": "hi"}
    status, body = _req(httpd.server_port, "/alert", method="POST", data=payload, token=None)
    assert status == 401


def test_auth_bad_token(server):
    httpd, mw, bridge = server
    payload = {"category": "ha-test", "message": "hi"}
    status, body = _req(httpd.server_port, "/alert", method="POST", data=payload, token="wrong")
    assert status == 401


def test_alert_success(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/alert", method="POST", data={"category": "ha-leak", "message": "water"})
    assert status == 200
    mw.assert_called()
    args = mw.call_args[0]
    assert "alert ha-leak water" in (args[-1] if len(args) else mw.call_args.kwargs.get("line", ""))


def test_alert_invalid_category(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/alert", method="POST", data={"category": "bad!", "message": "x"})
    assert status == 400


def test_alert_message_too_long(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/alert", method="POST", data={"category": "ha-x", "message": "a" * 501})
    assert status == 400


def test_alert_clear_empty(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/alert", method="POST", data={"category": "ha-leak", "message": ""})
    assert status == 200
    # ensure line is alert category only
    last_call = mw.call_args
    line = last_call[0][-1] if last_call[0] else last_call.kwargs.get("line")
    assert line == "alert ha-leak" or line.strip() == "alert ha-leak"


def test_status_success(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/status", method="POST", data={"key": "40_ha", "value": "ok"})
    assert status == 200
    last_call = mw.call_args
    line = last_call[0][-1] if last_call[0] else last_call.kwargs.get("line")
    assert "status 40_ha ok" in str(line)


def test_status_invalid_key(server):
    httpd, mw, bridge = server
    status, body = _req(httpd.server_port, "/status", method="POST", data={"key": "bad key", "value": "ok"})
    assert status == 400


def test_rate_limit(server, monkeypatch):
    httpd, mw, bridge_mod = server
    # fresh limiter with a real window; monkeypatch restores it after the test
    monkeypatch.setattr(bridge_mod, "_RATE_LIMITER", bridge_mod.RateLimiter(window=5.0))
    # first ok
    s1, _ = _req(httpd.server_port, "/alert", method="POST", data={"category": "ha-rl", "message": "m"})
    assert s1 == 200
    # immediate second -> 429
    s2, _ = _req(httpd.server_port, "/alert", method="POST", data={"category": "ha-rl", "message": "m2"})
    assert s2 == 429


def test_status_rate_limit(server, monkeypatch):
    httpd, mw, bridge_mod = server
    monkeypatch.setattr(bridge_mod, "_RATE_LIMITER", bridge_mod.RateLimiter(window=5.0))
    s1, _ = _req(httpd.server_port, "/status", method="POST", data={"key": "40_ha", "value": "ok"})
    assert s1 == 200
    # immediate second write for the same key -> 429
    s2, _ = _req(httpd.server_port, "/status", method="POST", data={"key": "40_ha", "value": "ok"})
    assert s2 == 429
    # a different key has its own bucket
    s3, _ = _req(httpd.server_port, "/status", method="POST", data={"key": "41_ha", "value": "ok"})
    assert s3 == 200
    # alerts are namespaced separately from status keys
    s4, _ = _req(httpd.server_port, "/alert", method="POST", data={"category": "40_ha", "message": "m"})
    assert s4 == 200


def test_body_cap(server):
    httpd, mw, bridge_mod = server
    # body larger than the 8192-byte cap must be rejected with 400
    body = b'{"category":"ha-x","message":"' + b"a" * 8192 + b'"}'
    status, resp = _post_raw(httpd.server_port, "/alert", body)
    assert status == 400
    assert resp["error"] == "invalid json"


def test_invalid_content_length(server):
    httpd, mw, bridge_mod = server
    # a non-numeric Content-Length must not crash the handler (400)
    status, resp = _post_raw(httpd.server_port, "/alert", b"", {"Content-Length": "not-a-number"})
    assert status == 400


def test_status_key_too_long(server):
    httpd, mw, bridge_mod = server
    status, body = _req(httpd.server_port, "/status", method="POST", data={"key": "k" * 65, "value": "ok"})
    assert status == 400


def test_valid_key_length_boundary(bridge):
    assert bridge.valid_key("k" * 64) is True
    assert bridge.valid_key("k" * 65) is False
    assert bridge.valid_key("has space") is False
    assert bridge.valid_key("line\nbreak") is False
    assert bridge.valid_key("") is False


def test_rate_limiter_bounded(bridge):
    rl = bridge.RateLimiter(window=0.0)
    for i in range(3000):
        assert rl.allow(f"key-{i}") is True
    # the dict must stay bounded via oldest-half eviction
    assert len(rl._last) <= bridge.MAX_RATE_KEYS + 1


def test_constant_time_compare(bridge):
    assert bridge.check_bearer("Bearer secret-token", "secret-token") is True
    assert bridge.check_bearer("Bearer wrong", "secret-token") is False
    assert bridge.check_bearer(None, "secret-token") is False
