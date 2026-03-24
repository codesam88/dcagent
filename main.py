"""
Delta Chat Echo Bot
-------------------
A simple echo bot built with the Delta Chat JSON-RPC Python bindings.

Usage
-----
# One-time setup: create a chatmail account and set the bot's display name
uv run dcagent init DCACCOUNT:https://nine.testrun.org/new
uv run dcagent config displayname "My Echo Bot"
uv run dcagent config selfstatus "I echo everything you say!"

# Get the invite link to add the bot to your Delta Chat app
uv run dcagent link

# Start listening and responding
uv run dcagent serve
"""

import logging

from deltabot_cli import BotCli
from deltachat2 import MsgData, events

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BOT_NAME = "dcagent"

# ---------------------------------------------------------------------------
# CLI setup
# ---------------------------------------------------------------------------

cli = BotCli("dcagent")


@cli.on(events.NewMessage)
def on_new_message(bot, accid: int, event) -> None:
    """Echo every incoming message back to the sender."""
    msg = event.msg

    # Ignore messages sent by the bot itself and empty messages
    if not msg.text or msg.is_bot:
        return

    logger.info("Received message in chat %s: %r", msg.chat_id, msg.text[:80])

    reply = MsgData(text=msg.text)
    bot.rpc.send_msg(accid, msg.chat_id, reply)


@cli.on(events.NewMessage(command="/help"))
def on_help(bot, accid: int, event) -> None:
    """Reply to /help with a short usage description."""
    msg = event.msg
    help_text = (
        f"👋 Hi! I am {DEFAULT_BOT_NAME}.\n\n"
        "I will echo back any message you send me.\n\n"
        "Commands:\n"
        "  /help  – show this message\n"
        "  /ping  – check that I'm alive\n"
    )
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text=help_text))


@cli.on(events.NewMessage(command="/ping"))
def on_ping(bot, accid: int, event) -> None:
    """Reply to /ping with a pong."""
    msg = event.msg
    bot.rpc.send_msg(accid, msg.chat_id, MsgData(text="Pong! 🏓"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    cli.start()


if __name__ == "__main__":
    main()
