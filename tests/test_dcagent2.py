"""Unit tests for agent.py and bot.py."""

import logging
from unittest.mock import MagicMock

import pytest

from dcagent.agent import _dispatch, _pipe_send
from dcagent.bot import APP_NAME, AgentError, _build_parser, _ensure_configured, _get_or_create_admin_chat

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args(["serve"])
    assert args.subcommand == "serve"
    assert args.logging == "info"
    assert args.account is None
    assert args.pipe is None


def test_parser_init():
    args = _build_parser().parse_args(["init", "DCACCOUNT:https://nine.testrun.org/new"])
    assert args.subcommand == "init"
    assert args.addr == "DCACCOUNT:https://nine.testrun.org/new"
    assert args.password is None


def test_parser_init_with_password():
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


def test_parser_admin_no_invite():
    args = _build_parser().parse_args(["admin"])
    assert args.subcommand == "admin"
    assert args.invite is None


def test_parser_admin_with_invite():
    args = _build_parser().parse_args(["admin", "https://i.delta.chat/#ABC"])
    assert args.subcommand == "admin"
    assert args.invite == "https://i.delta.chat/#ABC"


def test_parser_serve_pipe():
    args = _build_parser().parse_args(["serve", "--pipe", "/tmp/test.pipe"])
    assert args.pipe == "/tmp/test.pipe"


def test_parser_log_file():
    args = _build_parser().parse_args(["--log-file", "/tmp/dc.log", "serve"])
    assert args.log_file == "/tmp/dc.log"


def test_parser_log_file_default():
    args = _build_parser().parse_args(["serve"])
    assert args.log_file is None


# ---------------------------------------------------------------------------
# _dispatch / _pipe_send
# ---------------------------------------------------------------------------


def test_dispatch_send():
    rpc = MagicMock()
    _dispatch({"cmd": "send", "chat_id": 42, "text": "hello"}, accid=1, rpc=rpc)
    rpc.send_msg.assert_called_once()
    call_args = rpc.send_msg.call_args
    assert call_args[0][0] == 1  # accid
    assert call_args[0][1] == 42  # chat_id
    assert call_args[0][2].text == "hello"


def test_dispatch_unknown_command(caplog):
    rpc = MagicMock()
    with caplog.at_level(logging.WARNING, logger=APP_NAME):
        _dispatch({"cmd": "bogus"}, accid=1, rpc=rpc)
    assert "bogus" in caplog.text
    rpc.send_msg.assert_not_called()


def test_pipe_send_missing_chat_id(caplog):
    rpc = MagicMock()
    with caplog.at_level(logging.ERROR, logger=APP_NAME):
        _pipe_send(1, {"cmd": "send", "text": "hi"}, rpc)
    assert "missing" in caplog.text
    rpc.send_msg.assert_not_called()


def test_pipe_send_missing_text(caplog):
    rpc = MagicMock()
    with caplog.at_level(logging.ERROR, logger=APP_NAME):
        _pipe_send(1, {"cmd": "send", "chat_id": 5}, rpc)
    assert "missing" in caplog.text
    rpc.send_msg.assert_not_called()


# ---------------------------------------------------------------------------
# _get_or_create_admin_chat
# ---------------------------------------------------------------------------


def test_get_admin_chat_existing():
    rpc = MagicMock()
    rpc.get_config.return_value = "7"
    chatid = _get_or_create_admin_chat(rpc, accid=1)
    assert chatid == 7
    rpc.create_group_chat.assert_not_called()


def test_get_admin_chat_creates_new():
    rpc = MagicMock()
    rpc.get_config.return_value = None
    rpc.create_group_chat.return_value = 99
    chatid = _get_or_create_admin_chat(rpc, accid=1)
    assert chatid == 99
    rpc.create_group_chat.assert_called_once_with(1, "Bot Admins", True)
    rpc.set_config.assert_called_once_with(1, "ui.admin_chat", "99")


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


def test_first_accid_no_accounts_raises():
    from dcagent.bot import _first_accid

    rpc = MagicMock()
    rpc.get_all_account_ids.return_value = []
    args = _build_parser().parse_args(["serve"])
    with pytest.raises(AgentError, match="No accounts"):
        _first_accid(rpc, args)
