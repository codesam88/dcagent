"""Unit tests for agent.py and bot.py."""

from unittest.mock import MagicMock

import pytest

from dcagent.agent import _handle_alert_state, _socket_dispatch
from dcagent.bot import (
    AgentError,
    _add_admin_chat,
    _add_alert_chat,
    _build_parser,
    _ensure_configured,
    _get_account,
    _get_admin_chats,
    _get_alert_chats,
    _get_or_create_admin_chat,
    _get_or_create_alert_chat,
)

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args(["serve"])
    assert args.subcommand == "serve"
    assert args.log_level == "info"
    assert args.listen_socket is None
    assert args.listen_addr is None


def test_parser_init():
    args = _build_parser().parse_args(["init", "DCACCOUNT:https://nine.testrun.org/new"])
    assert args.subcommand == "init"
    assert args.addr == "DCACCOUNT:https://nine.testrun.org/new"
    assert args.password is None


def test_parser_init_force():
    args = _build_parser().parse_args(["init", "--force", "user@example.com"])
    assert args.force is True


def test_parser_init_no_force_default():
    args = _build_parser().parse_args(["init", "user@example.com"])
    assert args.force is False
    args = _build_parser().parse_args(["init", "user@example.com", "secret"])
    assert args.addr == "user@example.com"
    assert args.password == "secret"


def test_parser_config_get():
    args = _build_parser().parse_args(["config", "displayname"])
    assert args.key == "displayname"
    assert args.value is None


def test_parser_config_set():
    args = _build_parser().parse_args(["config", "displayname", "MyBot"])
    assert args.key == "displayname"
    assert args.value == "MyBot"


def test_parser_alert_no_invite():
    args = _build_parser().parse_args(["alert"])
    assert args.subcommand == "alert"
    assert args.invite is None


def test_parser_alert_with_invite():
    args = _build_parser().parse_args(["alert", "https://i.delta.chat/#ABC"])
    assert args.subcommand == "alert"
    assert args.invite == "https://i.delta.chat/#ABC"


def test_parser_admin_no_invite():
    args = _build_parser().parse_args(["admin"])
    assert args.subcommand == "admin"
    assert args.invite is None


def test_parser_admin_with_invite():
    args = _build_parser().parse_args(["admin", "https://i.delta.chat/#ABC"])
    assert args.subcommand == "admin"
    assert args.invite == "https://i.delta.chat/#ABC"


def test_parser_serve_socket_unix():
    args = _build_parser().parse_args(["serve", "--listen-socket", "/tmp/test.sock"])
    assert args.listen_socket == "/tmp/test.sock"
    assert args.listen_addr is None


def test_parser_serve_socket_inet():
    args = _build_parser().parse_args(["serve", "--listen-addr", "0.0.0.0:5000"])
    assert args.listen_addr == "0.0.0.0:5000"
    assert args.listen_socket is None


def test_parser_serve_socket_both():
    args = _build_parser().parse_args(["serve", "--listen-socket", "/tmp/test.sock", "--listen-addr", "0.0.0.0:5000"])
    assert args.listen_socket == "/tmp/test.sock"
    assert args.listen_addr == "0.0.0.0:5000"


def test_parser_log_file():
    args = _build_parser().parse_args(["--log-file", "/tmp/dc.log", "serve"])
    assert args.log_file == "/tmp/dc.log"


def test_parser_log_file_default():
    args = _build_parser().parse_args(["serve"])
    assert args.log_file is None


# _handle_alert_state
# ---------------------------------------------------------------------------


def test_handle_alert_state_immediate_category():
    """Category "" always sends, bypasses deduplication."""
    alert_map = {}
    result = _handle_alert_state("", "urgent alert", alert_map)
    assert result == "urgent alert"

    # Second call with same message should still send
    result = _handle_alert_state("", "urgent alert", alert_map)
    assert result == "urgent alert"


def test_handle_alert_state_first_alert():
    """First non-empty message should be sent."""
    alert_map = {}
    result = _handle_alert_state("disk", "95% full", alert_map)
    assert result == "disk: 95% full"


def test_handle_alert_state_no_change():
    """Same message should be suppressed."""
    alert_map = {"disk": "95% full"}
    result = _handle_alert_state("disk", "95% full", alert_map)
    assert result is None


def test_handle_alert_state_message_change():
    """Different message should be sent."""
    alert_map = {"disk": "95% full"}
    result = _handle_alert_state("disk", "98% full", alert_map)
    assert result == "disk: 98% full"


def test_handle_alert_state_recovery():
    """Empty message after error should send recovery."""
    alert_map = {"disk": "95% full"}
    result = _handle_alert_state("disk", "", alert_map)
    assert result == "disk: recovered (was: 95% full)"


def test_handle_alert_state_recovery_already_sent():
    """Empty message when already empty should be suppressed."""
    alert_map = {"disk": ""}
    result = _handle_alert_state("disk", "", alert_map)
    assert result is None


def test_handle_alert_state_first_empty():
    """First empty message should be suppressed."""
    alert_map = {}
    result = _handle_alert_state("disk", "", alert_map)
    assert result is None


def test_handle_alert_state_alert_after_recovery():
    """Alert after recovery should send normally."""
    alert_map = {"disk": ""}
    result = _handle_alert_state("disk", "92% full", alert_map)
    assert result == "disk: 92% full"


# ---------------------------------------------------------------------------
# _get_alert_chats / _add_alert_chat
# ---------------------------------------------------------------------------


def test_get_alert_chats_empty():
    rpc = MagicMock()
    rpc.get_config.return_value = None
    assert _get_alert_chats(rpc, accid=1) == []


def test_get_alert_chats_single():
    rpc = MagicMock()
    rpc.get_config.return_value = "42"
    assert _get_alert_chats(rpc, accid=1) == [42]


def test_get_alert_chats_multiple():
    rpc = MagicMock()
    rpc.get_config.return_value = "5,7,9"
    assert _get_alert_chats(rpc, accid=1) == [5, 7, 9]


def test_add_alert_chat_new():
    rpc = MagicMock()
    rpc.get_config.return_value = "5"
    _add_alert_chat(rpc, accid=1, chat_id=7)
    rpc.set_config.assert_called_once_with(1, "ui.alert_chats", "5,7")


def test_add_alert_chat_no_duplicate():
    rpc = MagicMock()
    rpc.get_config.return_value = "5,7"
    _add_alert_chat(rpc, accid=1, chat_id=7)
    rpc.set_config.assert_called_once_with(1, "ui.alert_chats", "5,7")


def test_get_or_create_alert_chat_existing():
    rpc = MagicMock()
    rpc.get_config.return_value = "42"
    chatid = _get_or_create_alert_chat(rpc, accid=1)
    assert chatid == 42
    rpc.create_group_chat.assert_not_called()


def test_get_or_create_alert_chat_creates_new():
    rpc = MagicMock()
    rpc.get_config.return_value = None
    rpc.create_group_chat.return_value = 55
    chatid = _get_or_create_alert_chat(rpc, accid=1)
    assert chatid == 55
    rpc.create_group_chat.assert_called_once_with(1, "Bot alerts", True)
    rpc.set_config.assert_called_once_with(1, "ui.alert_chats", "55")


# ---------------------------------------------------------------------------
# _get_admin_chats / _add_admin_chat / _get_or_create_admin_chat
# ---------------------------------------------------------------------------


def test_get_admin_chats_empty():
    rpc = MagicMock()
    rpc.get_config.return_value = None
    assert _get_admin_chats(rpc, accid=1) == []


def test_get_admin_chats_multiple():
    rpc = MagicMock()
    rpc.get_config.return_value = "3,7"
    assert _get_admin_chats(rpc, accid=1) == [3, 7]


def test_add_admin_chat_new():
    rpc = MagicMock()
    rpc.get_config.return_value = "3"
    _add_admin_chat(rpc, accid=1, chat_id=7)
    rpc.set_config.assert_called_once_with(1, "ui.admin_chats", "3,7")


def test_add_admin_chat_no_duplicate():
    rpc = MagicMock()
    rpc.get_config.return_value = "3,7"
    _add_admin_chat(rpc, accid=1, chat_id=7)
    rpc.set_config.assert_called_once_with(1, "ui.admin_chats", "3,7")


def test_get_or_create_admin_chat_existing():
    rpc = MagicMock()
    rpc.get_config.return_value = "7"
    chatid = _get_or_create_admin_chat(rpc, accid=1)
    assert chatid == 7
    rpc.create_group_chat.assert_not_called()


def test_get_or_create_admin_chat_creates_new():
    rpc = MagicMock()
    rpc.get_config.return_value = None
    rpc.create_group_chat.return_value = 99
    chatid = _get_or_create_admin_chat(rpc, accid=1)
    assert chatid == 99
    rpc.create_group_chat.assert_called_once_with(1, "Bot admins", True)
    rpc.set_config.assert_called_once_with(1, "ui.admin_chats", "99")


# ---------------------------------------------------------------------------
# AgentError / _ensure_configured
# ---------------------------------------------------------------------------


def test_ensure_configured_ok():
    rpc = MagicMock()
    rpc.is_configured.return_value = True
    _ensure_configured(rpc, accid=1)  # should not raise


def test_ensure_configured_raises():
    rpc = MagicMock()
    rpc.is_configured.return_value = False
    with pytest.raises(AgentError, match="not configured"):
        _ensure_configured(rpc, accid=1)


def test_get_account_no_accounts_raises():
    rpc = MagicMock()
    rpc.get_all_account_ids.return_value = []
    with pytest.raises(AgentError, match="No accounts"):
        _get_account(rpc)


# ---------------------------------------------------------------------------
# _socket_dispatch
# ---------------------------------------------------------------------------


def test_socket_dispatch_alert_success():
    """Socket alert dispatch should return ok response."""
    rpc = MagicMock()
    rpc.get_config.return_value = "42"
    alert_map = {}
    result = _socket_dispatch("alert disk 95% full", accid=1, rpc=rpc, status_map={}, alert_map=alert_map)
    assert "ok" in result
    assert "alert sent" in result


def test_socket_dispatch_alert_no_category():
    """Socket alert without category should return error."""
    result = _socket_dispatch("alert", accid=1, rpc=MagicMock(), status_map={}, alert_map={})
    assert "error" in result
    assert "requires category" in result


def test_socket_dispatch_status_success():
    """Socket status dispatch should return ok response."""
    rpc = MagicMock()
    status_map = {}
    result = _socket_dispatch("status cpu 45%", accid=1, rpc=rpc, status_map=status_map, alert_map={})
    assert "ok" in result
    assert "updated" in result
    assert status_map["cpu"] == "45%"


def test_socket_dispatch_status_missing_args():
    """Socket status without key and value should return error."""
    result = _socket_dispatch("status", accid=1, rpc=MagicMock(), status_map={}, alert_map={})
    assert "error" in result
    assert "requires a key and value" in result


def test_socket_dispatch_unknown_command():
    """Socket dispatch with unknown command should return error."""
    result = _socket_dispatch("unknown test", accid=1, rpc=MagicMock(), status_map={}, alert_map={})
    assert "error" in result
    assert "unknown command" in result
