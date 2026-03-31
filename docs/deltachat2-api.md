# deltachat2 Python API Reference

Concise reference for the `deltachat2` Python wrapper. For the full list of
RPC methods see [deltachat-rpc-api.md](deltachat-rpc-api.md).

---

## Setup

```python
from deltachat2 import IOTransport, Rpc, Bot, JsonRpcError

with IOTransport(accounts_dir="/path/to/accounts") as trans:
    rpc = Rpc(trans)
    # use rpc
```

`IOTransport` launches `deltachat-rpc-server` as a subprocess; pass extra
`subprocess.Popen` kwargs as `**kwargs` (e.g. `stderr=subprocess.DEVNULL`).

---

## Key RPC calls

All methods are dispatched dynamically via `Rpc.__getattr__`; snake_case
Python names map automatically to camelCase JSON-RPC.

```python
# Accounts
accid = rpc.add_account()
rpc.is_configured(accid)                         # → bool
rpc.get_all_account_ids()                        # → list[int]
rpc.get_system_info().deltachat_core_version     # → str

# Config
rpc.set_config(accid, "bot", "1")
rpc.get_config(accid, "configured_addr")         # → str | None
rpc.list_transports(accid)                       # → list[dict]  (each has "addr")
rpc.add_transport_from_qr(accid, qr_data)        # DCACCOUNT: URIs
rpc.add_or_update_transport(accid, {"addr": ..., "password": ...})

# IO
rpc.start_io(accid)
rpc.start_io_for_all_accounts()
rpc.stop_io_for_all_accounts()

# Messages & chats
rpc.send_msg(accid, chatid, MsgData(text="hi"))  # → int msgid
rpc.create_group_chat(accid, "name", verified)   # → int chatid
rpc.get_chat_securejoin_qr_code(accid, chatid)   # chatid=None → personal invite
rpc.secure_join(accid, qr_data)                  # → int chatid
```

Notable config keys: `"bot"` (set `"1"`), `"displayname"`, `"selfstatus"`,
`"selfavatar"`, `"configured_addr"`, `"ui.admin_chat"`,
`"sys.config_keys"` (space-separated list of all keys).

---

## Types

### MsgData (dataclass)
```python
@dataclass
class MsgData:
    text: str | None = None
    html: str | None = None
    viewtype: MessageViewtype | None = None
    file: str | None = None
    location: tuple[float, float] | None = None
    override_sender_name: str | None = None
    quoted_message_id: int | None = None
```

### Message (AttrDict)
Key attributes: `.id`, `.chat_id`, `.from_id`, `.text`, `.html`,
`.viewtype`, `.state` (`MessageState`), `.timestamp`, `.is_bot` (bool),
`.is_info` (bool), `.is_forwarded`, `.file`, `.file_mime`, `.file_name`.

### CoreEvent (AttrDict)
`.kind` (`EventType`), plus kind-specific fields:
- `CONFIGURE_PROGRESS`: `.progress` (0–1000, 0=fail), `.comment`
- `SECUREJOIN_JOINER_PROGRESS`: `.progress` (0–1000, 0=fail), `.contact_id`
- `INCOMING_MSG` / `MSGS_CHANGED`: `.chat_id`, `.msg_id`
- `INFO` / `WARNING` / `ERROR`: `.msg`

### SpecialContactId (IntEnum)
`SELF=1`, `INFO=2`, `DEVICE=5`, `LAST_SPECIAL=9`.
Messages from real contacts have `from_id > LAST_SPECIAL`.

---

## Bot class

```python
bot = Bot(rpc, hooks=[(handler_fn, EventFilter)], logger=my_logger)
bot.run_forever(account_id=0)   # 0 = all accounts
bot.run_until(lambda event: bool, account_id=0)
bot.add_hook(fn, EventFilter)
bot.remove_hook(fn, EventFilter)
```

`Bot` sets `bot=1` on account (not automatically — do it manually).
`Bot.logger` defaults to `logging.getLogger("deltachat2.Bot")` — propagates
to root logger normally.

Event handler signature: `def handler(bot, accid: int, event: NewMsgEvent) -> None`

### NewMessage filter (events.py)
```python
from deltachat2 import events

events.NewMessage(
    pattern=None,          # str | re.Pattern | callable
    command=None,          # str e.g. "/help" — implies is_info=False
    is_bot=False,          # False=users only, True=bots only, None=all
    is_outgoing=False,     # False=incoming only, True=outgoing, None=both
    is_info=None,          # True=system msgs only, False=exclude system msgs
    func=None,             # custom callable(NewMsgEvent) -> bool
)
```

**`is_bot` defaults to `False`** — bots' messages are filtered unless
`is_bot=None` or `is_bot=True`.

### RawEvent filter
```python
events.RawEvent(types=[EventType.INCOMING_MSG, ...], func=None)
```
Handler signature: `def handler(client, accid: int, event: CoreEvent) -> None`

---

## Event loop internals

`Bot.run_until` (overrides `Client.run_until`):
1. Calls `start_io(accid)` or `start_io_for_all_accounts()`
2. Drains pending messages via `_process_messages(accid)`
3. Loops on `get_next_event()`, on `INCOMING_MSG`/`MSGS_CHANGED` calls
   `_process_messages` which calls registered `NewMessage` hooks

`_process_messages` skips messages where `from_id <= SpecialContactId.LAST_SPECIAL`
unless outgoing (`from_id == SELF`).
