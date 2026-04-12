"""Unit tests for agent.py and bot.py."""

import logging
from unittest.mock import MagicMock

import pytest

from dcagent.agent import _pipe_do_alert
from dcagent.bot import (
    APP_NAME,
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
    assert args.pipe_path is None


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


def test_parser_serve_pipe():
    args = _build_parser().parse_args(["serve", "--pipe-path", "/tmp/test.pipe"])
    assert args.pipe_path == "/tmp/test.pipe"


def test_parser_log_file():
    args = _build_parser().parse_args(["--log-file", "/tmp/dc.log", "serve"])
    assert args.log_file == "/tmp/dc.log"


def test_parser_log_file_default():
    args = _build_parser().parse_args(["serve"])
    assert args.log_file is None


# ---------------------------------------------------------------------------
# _pipe_do_alert
# ---------------------------------------------------------------------------


def test_pipe_do_alert_sends_to_alert_chats():
    rpc = MagicMock()
    rpc.get_config.return_value = "42"
    _pipe_do_alert("hello", accid=1, rpc=rpc)
    rpc.send_msg.assert_called_once()
    call_args = rpc.send_msg.call_args
    assert call_args[0][0] == 1  # accid
    assert call_args[0][1] == 42  # chat_id
    assert call_args[0][2].text == "hello"


def test_pipe_do_alert_no_alert_chats(caplog):
    rpc = MagicMock()
    rpc.get_config.return_value = None
    with caplog.at_level(logging.WARNING, logger=APP_NAME):
        _pipe_do_alert("hi", accid=1, rpc=rpc)
    assert "no alert chats" in caplog.text
    rpc.send_msg.assert_not_called()


def test_pipe_do_alert_multiple_chats():
    rpc = MagicMock()
    rpc.get_config.return_value = "5,7,9"
    _pipe_do_alert("hi", accid=1, rpc=rpc)
    assert rpc.send_msg.call_count == 3


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
