# Delta Chat JSON-RPC API

> Generated from `deltachat-rpc-server --openrpc` · core version **1.0.0**
> Re-run `make docs` after `uv sync` to update.

The RPC methods below are called via `rpc.<method_name>(...)` using the
`deltachat2.Rpc` dynamic dispatcher (snake_case args map to camelCase JSON).

## Table of contents

- [Accounts](#accounts)
- [Chats](#chats)
- [Contacts](#contacts)
- [Messages](#messages)
- [Configuration](#configuration)
- [Transport](#transport)
- [Backup & import/export](#backup-import-export)
- [Webxdc](#webxdc)
- [Locations](#locations)
- [Provider info](#provider-info)
- [IO & network](#io-network)
- [Events](#events)
- [Miscellaneous](#miscellaneous)

## Accounts

### `add_account`

```
rpc.add_account() → uint32
```

### `forward_messages_to_account`

```
rpc.forward_messages_to_account(src_account_id: uint32, src_message_ids: list[uint32], dst_account_id: uint32, dst_chat_id: uint32) → None
```

Forward messages to a chat in another account.
 See [`Self::forward_messages`] for more info.

| Param | Type | Required |
|-------|------|----------|
| `srcAccountId` | `uint32` | ✓ |
| `srcMessageIds` | `list[uint32]` | ✓ |
| `dstAccountId` | `uint32` | ✓ |
| `dstChatId` | `uint32` | ✓ |

### `get_account_file_size`

```
rpc.get_account_file_size(account_id: uint32) → uint64
```

Get the combined filesize of an account in bytes

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_account_info`

```
rpc.get_account_info(account_id: uint32) → Account
```

Get top-level info for an account.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_all_account_ids`

```
rpc.get_all_account_ids() → list[uint32]
```

### `get_all_accounts`

```
rpc.get_all_accounts() → list[Account]
```

Get a list of all configured accounts.

### `get_selected_account_id`

```
rpc.get_selected_account_id() → integer | null
```

Get the selected account from the account manager (on startup it is read from accounts.toml)

### `migrate_account`

```
rpc.migrate_account(path_to_db: str) → uint32
```

Imports/migrated an existing account from a database path into this account manager.
 Returns the ID of new account.

| Param | Type | Required |
|-------|------|----------|
| `pathToDb` | `str` | ✓ |

### `remove_account`

```
rpc.remove_account(account_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `select_account`

```
rpc.select_account(id: uint32) → None
```

Select account in account manager, this saves the last used account to accounts.toml

| Param | Type | Required |
|-------|------|----------|
| `id` | `uint32` | ✓ |

### `set_accounts_order`

```
rpc.set_accounts_order(order: list[uint32]) → None
```

Set the order of accounts.
 The provided list should contain all account IDs in the desired order.
 If an account ID is missing from the list, it will be appended at the end.
 If the list contains non-existent account IDs, they will be ignored.

| Param | Type | Required |
|-------|------|----------|
| `order` | `list[uint32]` | ✓ |

### `start_io_for_all_accounts`

```
rpc.start_io_for_all_accounts() → None
```

Starts background tasks for all accounts.

### `stop_io_for_all_accounts`

```
rpc.stop_io_for_all_accounts() → None
```

Stops background tasks for all accounts.

## Chats

### `accept_chat`

```
rpc.accept_chat(account_id: uint32, chat_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `block_chat`

```
rpc.block_chat(account_id: uint32, chat_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `create_group_chat`

```
rpc.create_group_chat(account_id: uint32, name: str, protect: bool) → uint32
```

Create a new encrypted group chat (with key-contacts).

 After creation,
 the group has one member with the ID DC_CONTACT_ID_SELF
 and is in _unpromoted_ state.
 This means, you can add or remove members, change the name,
 the group image and so on without messages being sent to all group members.

 This changes as soon as the first message is sent to the group members
 and the group becomes _promoted_.
 After that, all changes are synced with all group members
 by sending status message.

 To check, if a chat is still unpromoted, you can look at the `is_unpromoted` property of `BasicChat` or `FullChat`.
 This may be useful if you want to show some help for just created groups.

 `protect` argument is deprecated as of 2025-10-22 and is left for compatibility.
 Pass `false` here.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `name` | `str` | ✓ |
| `protect` | `bool` | ✓ |

### `create_group_chat_unencrypted`

```
rpc.create_group_chat_unencrypted(account_id: uint32, name: str) → uint32
```

Create a new unencrypted group chat.

 Same as [`Self::create_group_chat`], but the chat is unencrypted and can only have
 address-contacts.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `name` | `str` | ✓ |

### `delete_chat`

```
rpc.delete_chat(account_id: uint32, chat_id: uint32) → None
```

Delete a chat.

 Messages are deleted from the device and the chat database entry is deleted.
 After that, a `MsgsChanged` event is emitted.
 Messages are deleted from the server in background.

 Things that are _not done_ implicitly:

 - The chat or the contact is **not blocked**, so new messages from the user/the group may appear as a contact request
   and the user may create the chat again.
 - **Groups are not left** - this would
   be unexpected as (1) deleting a normal chat also does not prevent new mails
   from arriving, (2) leaving a group requires sending a message to
   all group members - especially for groups not used for a longer time, this is
   really unexpected when deletion results in contacting all members again,
   (3) only leaving groups is also a valid usecase.

 To leave a chat explicitly, use leave_group()

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_basic_chat_info`

```
rpc.get_basic_chat_info(account_id: uint32, chat_id: uint32) → BasicChat
```

get basic info about a chat,
 use chatlist_get_full_chat_by_id() instead if you need more information

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_chat_description`

```
rpc.get_chat_description(account_id: uint32, chat_id: uint32) → str
```

Load the chat description from the database.

 UIs show this in the profile page of the chat,
 it is settable by [`Self::set_chat_description`] / `setChatDescription()`.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_chat_encryption_info`

```
rpc.get_chat_encryption_info(account_id: uint32, chat_id: uint32) → str
```

Get encryption info for a chat.
 Get a multi-line encryption info, containing encryption preferences of all members.
 Can be used to find out why messages sent to group are not encrypted.

 returns Multi-line text

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_chat_ephemeral_timer`

```
rpc.get_chat_ephemeral_timer(account_id: uint32, chat_id: uint32) → uint32
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_chat_media`

```
rpc.get_chat_media(account_id: uint32, chat_id: integer | null, message_type: Viewtype, or_message_type2: Viewtype | None, or_message_type3: Viewtype | None) → list[uint32]
```

Returns all message IDs of the given types in a chat.
 Typically used to show a gallery.

 The list is already sorted and starts with the oldest message.
 Clients should not try to re-sort the list as this would be an expensive action
 and would result in inconsistencies between clients.

 Setting `chat_id` to `None` (`null` in typescript) means get messages with media
 from any chat of the currently used account.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `integer | null` | ✓ |
| `messageType` | `Viewtype` | ✓ |
| `orMessageType2` | `Viewtype | None` | ✓ |
| `orMessageType3` | `Viewtype | None` | ✓ |

### `get_chat_securejoin_qr_code`

```
rpc.get_chat_securejoin_qr_code(account_id: uint32, chat_id: integer | null) → str
```

Get QR code text that will offer a [SecureJoin](https://securejoin.delta.chat/) invitation.

 If `chat_id` is a group chat ID, SecureJoin QR code for the group is returned.
 If `chat_id` is unset, setup contact QR code is returned.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `integer | null` | ✓ |

### `get_chat_securejoin_qr_code_svg`

```
rpc.get_chat_securejoin_qr_code_svg(account_id: uint32, chat_id: integer | null) → tuple[str, str]
```

Get QR code (text and SVG) that will offer a Setup-Contact or Verified-Group invitation.
 The QR code is compatible to the OPENPGP4FPR format
 so that a basic fingerprint comparison also works e.g. with OpenKeychain.

 The scanning device will pass the scanned content to `checkQr()` then;
 if `checkQr()` returns `askVerifyContact` or `askVerifyGroup`
 an out-of-band-verification can be joined using `secure_join()`

 @deprecated as of 2026-03; use create_qr_svg(get_chat_securejoin_qr_code()) instead.

 chat_id: If set to a group-chat-id,
     the Verified-Group-Invite protocol is offered in the QR code;
     works for protected groups as well as for normal groups.
     If not set, the Setup-Contact protocol is offered in the QR code.
     See https://securejoin.delta.chat/ for details about both protocols.

 return format: `[code, svg]`

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `integer | null` | ✓ |

### `get_chatlist_entries`

```
rpc.get_chatlist_entries(account_id: uint32, list_flags: integer | null, query_string: string | null, query_contact_id: integer | null) → list[uint32]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `listFlags` | `integer | null` | ✓ |
| `queryString` | `string | null` | ✓ |
| `queryContactId` | `integer | null` | ✓ |

### `get_chatlist_items_by_entries`

```
rpc.get_chatlist_items_by_entries(account_id: uint32, entries: list[uint32]) → dict[str, ChatListItemFetchResult]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `entries` | `list[uint32]` | ✓ |

### `get_first_unread_message_of_chat`

```
rpc.get_first_unread_message_of_chat(account_id: uint32, chat_id: uint32) → integer | null
```

Returns the message that is immediately followed by the last seen
 message.
 From the point of view of the user this is effectively
 "first unread", but in reality in the database a seen message
 _can_ be followed by a fresh (unseen) message
 if that message has not been individually marked as seen.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_full_chat_by_id`

```
rpc.get_full_chat_by_id(account_id: uint32, chat_id: uint32) → FullChat
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_similar_chat_ids`

```
rpc.get_similar_chat_ids(account_id: uint32, chat_id: uint32) → list[uint32]
```

Returns chats similar to the given one.

 Experimental API, subject to change without notice.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `is_chat_muted`

```
rpc.is_chat_muted(account_id: uint32, chat_id: uint32) → bool
```

Check whether the chat is currently muted (can be changed by set_chat_mute_duration()).

 This is available as a standalone function outside of fullchat, because it might be only needed for notification

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `marknoticed_all_chats`

```
rpc.marknoticed_all_chats(account_id: uint32) → None
```

Mark all messages in all chats as _noticed_.
 Skips messages from blocked contacts, but does not skip messages in muted chats.

 _Noticed_ messages are no longer _fresh_ and do not count as being unseen
 but are still waiting for being marked as "seen" using markseen_msgs()
 (read receipts aren't sent for noticed messages).

 Calling this function usually results in the event #DC_EVENT_MSGS_NOTICED.
 See also markseen_msgs().

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `marknoticed_chat`

```
rpc.marknoticed_chat(account_id: uint32, chat_id: uint32) → None
```

Mark all messages in a chat as _noticed_.
  _Noticed_ messages are no longer _fresh_ and do not count as being unseen
  but are still waiting for being marked as "seen" using markseen_msgs()
  (read receipts aren't sent for noticed messages).

  Calling this function usually results in the event #DC_EVENT_MSGS_NOTICED.
  See also markseen_msgs().

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `set_chat_description`

```
rpc.set_chat_description(account_id: uint32, chat_id: uint32, description: str) → None
```

Set group or broadcast channel description.

 If the group is already _promoted_ (any message was sent to the group),
 or if this is a brodacast channel,
 all members are informed by a special status message that is sent automatically by this function.

 Sends out #DC_EVENT_CHAT_MODIFIED and #DC_EVENT_MSGS_CHANGED if a status message was sent.

 See also [`Self::get_chat_description`] / `getChatDescription()`.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `description` | `str` | ✓ |

### `set_chat_ephemeral_timer`

```
rpc.set_chat_ephemeral_timer(account_id: uint32, chat_id: uint32, timer: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `timer` | `uint32` | ✓ |

### `set_chat_mute_duration`

```
rpc.set_chat_mute_duration(account_id: uint32, chat_id: uint32, duration: MuteDuration) → None
```

Set mute duration of a chat.

 The UI can then call is_chat_muted() when receiving a new message
 to decide whether it should trigger an notification.

 Muted chats should not sound or vibrate
 and should not show a visual notification in the system area.
 Moreover, muted chats should be excluded from global badge counter
 (get_fresh_msgs() skips muted chats therefore)
 and the in-app, per-chat badge counter should use a less obtrusive color.

 Sends out #DC_EVENT_CHAT_MODIFIED.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `duration` | `MuteDuration` | ✓ |

### `set_chat_name`

```
rpc.set_chat_name(account_id: uint32, chat_id: uint32, new_name: str) → None
```

Set group name.

 If the group is already _promoted_ (any message was sent to the group),
 or if this is a brodacast channel,
 all members are informed by a special status message that is sent automatically by this function.

 Sends out #DC_EVENT_CHAT_MODIFIED and #DC_EVENT_MSGS_CHANGED if a status message was sent.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `newName` | `str` | ✓ |

### `set_chat_profile_image`

```
rpc.set_chat_profile_image(account_id: uint32, chat_id: uint32, image_path: string | null) → None
```

Set group profile image.

 If the group is already _promoted_ (any message was sent to the group),
 or if this is a brodacast channel,
 all members are informed by a special status message that is sent automatically by this function.

 Sends out #DC_EVENT_CHAT_MODIFIED and #DC_EVENT_MSGS_CHANGED if a status message was sent.

 To find out the profile image of a chat, use dc_chat_get_profile_image()

 @param image_path Full path of the image to use as the group image. The image will immediately be copied to the
     `blobdir`; the original image will not be needed anymore.
      If you pass null here, the group image is deleted (for promoted groups, all members are informed about
      this change anyway).

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `imagePath` | `string | null` | ✓ |

### `set_chat_visibility`

```
rpc.set_chat_visibility(account_id: uint32, chat_id: uint32, visibility: ChatVisibility) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `visibility` | `ChatVisibility` | ✓ |

## Contacts

### `add_contact_to_chat`

```
rpc.add_contact_to_chat(account_id: uint32, chat_id: uint32, contact_id: uint32) → None
```

Add a member to a group.

 If the group is already _promoted_ (any message was sent to the group),
 all group members are informed by a special status message that is sent automatically by this function.

 If the group has group protection enabled, only verified contacts can be added to the group.

 Sends out #DC_EVENT_CHAT_MODIFIED and #DC_EVENT_MSGS_CHANGED if a status message was sent.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `block_contact`

```
rpc.block_contact(account_id: uint32, contact_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `change_contact_name`

```
rpc.change_contact_name(account_id: uint32, contact_id: uint32, name: str) → None
```

Sets display name for existing contact.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |
| `name` | `str` | ✓ |

### `check_qr`

```
rpc.check_qr(account_id: uint32, qr_content: str) → Qr
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qrContent` | `str` | ✓ |

### `create_chat_by_contact_id`

```
rpc.create_chat_by_contact_id(account_id: uint32, contact_id: uint32) → uint32
```

Returns contact id of the created or existing DM chat with that contact

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `create_contact`

```
rpc.create_contact(account_id: uint32, email: str, name: string | null) → uint32
```

Add a single contact as a result of an explicit user action.

 This will always create or look up an address-contact,
 i.e. a contact identified by an email address,
 with all messages sent to and from this contact being unencrypted.
 If the user just clicked on an email address,
 you should first check [`Self::lookup_contact_id_by_addr`]/`lookupContactIdByAddr.`,
 and only if there is no contact yet, call this function here.

 Returns contact id of the created or existing contact.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `email` | `str` | ✓ |
| `name` | `string | null` | ✓ |

### `create_qr_svg`

```
rpc.create_qr_svg(text: str) → str
```

Renders the given text as a QR code SVG image.

| Param | Type | Required |
|-------|------|----------|
| `text` | `str` | ✓ |

### `delete_contact`

```
rpc.delete_contact(account_id: uint32, contact_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `get_blocked_contacts`

```
rpc.get_blocked_contacts(account_id: uint32) → list[Contact]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_chat_contacts`

```
rpc.get_chat_contacts(account_id: uint32, chat_id: uint32) → list[uint32]
```

Get the contact IDs belonging to a chat.

 - for normal chats, the function always returns exactly one contact,
   DC_CONTACT_ID_SELF is returned only for SELF-chats.

 - for group chats all members are returned, DC_CONTACT_ID_SELF is returned
   explicitly as it may happen that oneself gets removed from a still existing
   group

 - for broadcast channels, all recipients are returned, DC_CONTACT_ID_SELF is not included

 - for mailing lists, the behavior is not documented currently, we will decide on that later.
   for now, the UI should not show the list for mailing lists.
   (we do not know all members and there is not always a global mailing list address,
   so we could return only SELF or the known members; this is not decided yet)

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_chat_id_by_contact_id`

```
rpc.get_chat_id_by_contact_id(account_id: uint32, contact_id: uint32) → integer | null
```

Returns the [`ChatId`] for the 1:1 chat with `contact_id` if it exists.

 If it does not exist, `None` is returned.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `get_contact`

```
rpc.get_contact(account_id: uint32, contact_id: uint32) → Contact
```

Get a single contact options by ID.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `get_contact_encryption_info`

```
rpc.get_contact_encryption_info(account_id: uint32, contact_id: uint32) → str
```

Get encryption info for a contact.
 Get a multi-line encryption info, containing your fingerprint and the
 fingerprint of the contact, used e.g. to compare the fingerprints for a simple out-of-band verification.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `get_contact_ids`

```
rpc.get_contact_ids(account_id: uint32, list_flags: uint32, query: string | null) → list[uint32]
```

Returns ids of known and unblocked contacts.

 By default, key-contacts are listed.

 * `list_flags` - A combination of flags:
   - `DC_GCL_ADD_SELF` - Add SELF unless filtered by other parameters.
   - `DC_GCL_ADDRESS` - List address-contacts instead of key-contacts.
 * `query` - A string to filter the list.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `listFlags` | `uint32` | ✓ |
| `query` | `string | null` | ✓ |

### `get_contacts`

```
rpc.get_contacts(account_id: uint32, list_flags: uint32, query: string | null) → list[Contact]
```

Returns known and unblocked contacts.

 Formerly called `getContacts2` in Desktop.
 See [`Self::get_contact_ids`] for parameters and more info.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `listFlags` | `uint32` | ✓ |
| `query` | `string | null` | ✓ |

### `get_contacts_by_ids`

```
rpc.get_contacts_by_ids(account_id: uint32, ids: list[uint32]) → dict[str, Contact]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `ids` | `list[uint32]` | ✓ |

### `get_past_chat_contacts`

```
rpc.get_past_chat_contacts(account_id: uint32, chat_id: uint32) → list[uint32]
```

Returns contact IDs of the past chat members.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `lookup_contact_id_by_addr`

```
rpc.lookup_contact_id_by_addr(account_id: uint32, addr: str) → integer | null
```

Looks up a known and unblocked contact with a given e-mail address.
 To get a list of all known and unblocked contacts, use contacts_get_contacts().

 **POTENTIAL SECURITY ISSUE**: If there are multiple contacts with this address
 (e.g. an address-contact and a key-contact),
 this looks up the most recently seen contact,
 i.e. which contact is returned depends on which contact last sent a message.
 If the user just clicked on a mailto: link, then this is the best thing you can do.
 But **DO NOT** internally represent contacts by their email address
 and do not use this function to look them up;
 otherwise this function will sometimes look up the wrong contact.
 Instead, you should internally represent contacts by their ids.

 To validate an e-mail address independently of the contact database
 use check_email_validity().

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `addr` | `str` | ✓ |

### `make_vcard`

```
rpc.make_vcard(account_id: uint32, contacts: list[uint32]) → str
```

Returns a vCard containing contacts with the given ids.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contacts` | `list[uint32]` | ✓ |

### `parse_vcard`

```
rpc.parse_vcard(path: str) → list[VcardContact]
```

Parses a vCard file located at the given path. Returns contacts in their original order.

| Param | Type | Required |
|-------|------|----------|
| `path` | `str` | ✓ |

### `remove_contact_from_chat`

```
rpc.remove_contact_from_chat(account_id: uint32, chat_id: uint32, contact_id: uint32) → None
```

Remove a member from a group.

 If the group is already _promoted_ (any message was sent to the group),
 all group members are informed by a special status message that is sent automatically by this function.

 Sends out #DC_EVENT_CHAT_MODIFIED and #DC_EVENT_MSGS_CHANGED if a status message was sent.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

### `set_config_from_qr`

```
rpc.set_config_from_qr(account_id: uint32, qr_content: str) → None
```

Set configuration values from a QR code (technically from the URI stored in it).
 Before this function is called, `check_qr()` should be used to get the QR code type.

 "DCACCOUNT:" and "DCLOGIN:" QR codes configure the account, but I/O mustn't be started for
 such QR codes, consider using [`Self::add_transport_from_qr`] which also restarts I/O.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qrContent` | `str` | ✓ |

### `set_draft_vcard`

```
rpc.set_draft_vcard(account_id: uint32, msg_id: uint32, contacts: list[uint32]) → None
```

Sets vCard containing the given contacts to the message draft.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |
| `contacts` | `list[uint32]` | ✓ |

### `unblock_contact`

```
rpc.unblock_contact(account_id: uint32, contact_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `contactId` | `uint32` | ✓ |

## Messages

### `add_device_message`

```
rpc.add_device_message(account_id: uint32, label: str, msg: MessageData | None) → integer | null
```

Add a message to the device-chat.
 Device-messages usually contain update information
 and some hints that are added during the program runs, multi-device etc.
 The device-message may be defined by a label;
 if a message with the same label was added or skipped before,
 the message is not added again, even if the message was deleted in between.
 If needed, the device-chat is created before.

 Sends the `MsgsChanged` event on success.

 Setting msg to None will prevent the device message with this label from being added in the future.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `label` | `str` | ✓ |
| `msg` | `MessageData | None` | ✓ |

### `delete_messages`

```
rpc.delete_messages(account_id: uint32, message_ids: list[uint32]) → None
```

Delete messages. The messages are deleted on the current device and
 on the IMAP server.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `delete_messages_for_all`

```
rpc.delete_messages_for_all(account_id: uint32, message_ids: list[uint32]) → None
```

Delete messages. The messages are deleted on the current device,
 on the IMAP server and also for all chat members

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `download_full_message`

```
rpc.download_full_message(account_id: uint32, message_id: uint32) → None
```

Asks the core to start downloading a message fully.
 This function is typically called when the user hits the "Download" button
 that is shown by the UI in case `download_state` is `'Available'` or `'Failure'`

 On success, the @ref DC_MSG "view type of the message" may change
 or the message may be replaced completely by one or more messages with other message IDs.
 That may happen e.g. in cases where the message was encrypted
 and the type could not be determined without fully downloading.
 Downloaded content can be accessed as usual after download.

 To reflect these changes a @ref DC_EVENT_MSGS_CHANGED event will be emitted.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `forward_messages`

```
rpc.forward_messages(account_id: uint32, message_ids: list[uint32], chat_id: uint32) → None
```

Forward messages to another chat.

 All types of messages can be forwarded,
 however, they will be flagged as such (dc_msg_is_forwarded() is set).

 Original sender, info-state and webxdc updates are not forwarded on purpose.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_existing_msg_ids`

```
rpc.get_existing_msg_ids(account_id: uint32, msg_ids: list[uint32]) → list[uint32]
```

Checks if the messages with given IDs exist.

 Returns IDs of existing messages.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgIds` | `list[uint32]` | ✓ |

### `get_fresh_msg_cnt`

```
rpc.get_fresh_msg_cnt(account_id: uint32, chat_id: uint32) → uint
```

Get the number of _fresh_ messages in a chat.
 Typically used to implement a badge with a number in the chatlist.

 If the specified chat is muted,
 the UI should show the badge counter "less obtrusive",
 e.g. using "gray" instead of "red" color.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_fresh_msgs`

```
rpc.get_fresh_msgs(account_id: uint32) → list[uint32]
```

Returns the message IDs of all _fresh_ messages of any chat.
 Typically used for implementing notification summaries
 or badge counters e.g. on the app icon.
 The list is already sorted and starts with the most recent fresh message.

 Messages belonging to muted chats or to the contact requests are not returned;
 these messages should not be notified
 and also badge counters should not include these messages.

 To get the number of fresh messages for a single chat, muted or not,
 use `get_fresh_msg_cnt()`.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_message`

```
rpc.get_message(account_id: uint32, msg_id: uint32) → Message
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |

### `get_message_html`

```
rpc.get_message_html(account_id: uint32, message_id: uint32) → string | null
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_ids`

```
rpc.get_message_ids(account_id: uint32, chat_id: uint32, info_only: bool, add_daymarker: bool) → list[uint32]
```

Returns all messages of a particular chat.

 * `add_daymarker` - If `true`, add day markers as `DC_MSG_ID_DAYMARKER` to the result,
   e.g. [1234, 1237, 9, 1239]. The day marker timestamp is the midnight one for the
   corresponding (following) day in the local timezone.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `infoOnly` | `bool` | ✓ |
| `addDaymarker` | `bool` | ✓ |

### `get_message_info`

```
rpc.get_message_info(account_id: uint32, message_id: uint32) → str
```

Get an informational text for a single message. The text is multiline and may
 contain e.g. the raw text of the message.

 The max. text returned is typically longer (about 100000 characters) than the
 max. text returned by dc_msg_get_text() (about 30000 characters).

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_info_object`

```
rpc.get_message_info_object(account_id: uint32, message_id: uint32) → MessageInfo
```

Returns additional information for single message.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_list_items`

```
rpc.get_message_list_items(account_id: uint32, chat_id: uint32, info_only: bool, add_daymarker: bool) → list[MessageListItem]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `infoOnly` | `bool` | ✓ |
| `addDaymarker` | `bool` | ✓ |

### `get_message_notification_info`

```
rpc.get_message_notification_info(account_id: uint32, message_id: uint32) → MessageNotificationInfo
```

Fetch info desktop needs for creating a notification for a message

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_reactions`

```
rpc.get_message_reactions(account_id: uint32, message_id: uint32) → Reactions | None
```

Returns reactions to the message.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_read_receipt_count`

```
rpc.get_message_read_receipt_count(account_id: uint32, message_id: uint32) → uint
```

Returns count of read receipts on message.

 This view count is meant as a feedback measure for the channel owner only.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_message_read_receipts`

```
rpc.get_message_read_receipts(account_id: uint32, message_id: uint32) → list[MessageReadReceipt]
```

Returns contacts that sent read receipts and the time of reading.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |

### `get_messages`

```
rpc.get_messages(account_id: uint32, message_ids: list[uint32]) → dict[str, MessageLoadResult]
```

get multiple messages in one call,
 if loading one message fails the error is stored in the result object in it's place.

 this is the batch variant of [get_message]

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `get_next_msgs`

```
rpc.get_next_msgs(account_id: uint32) → list[uint32]
```

Gets messages to be processed by the bot and returns their IDs.

 Only messages with database ID higher than `last_msg_id` config value
 are returned. After processing the messages, the bot should
 update `last_msg_id` by calling [`markseen_msgs`]
 or manually updating the value to avoid getting already
 processed messages.

 [`markseen_msgs`]: Self::markseen_msgs

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `markseen_msgs`

```
rpc.markseen_msgs(account_id: uint32, msg_ids: list[uint32]) → None
```

Mark messages as presented to the user.
 Typically, UIs call this function on scrolling through the message list,
 when the messages are presented at least for a little moment.
 The concrete action depends on the type of the chat and on the users settings
 (dc_msgs_presented() may be a better name therefore, but well. :)

 - For normal chats, the IMAP state is updated, MDN is sent
   (if set_config()-options `mdns_enabled` is set)
   and the internal state is changed to @ref DC_STATE_IN_SEEN to reflect these actions.

 - For contact requests, no IMAP or MDNs is done
   and the internal state is not changed therefore.
   See also marknoticed_chat().

 Moreover, timer is started for incoming ephemeral messages.
 This also happens for contact requests chats.

 This function updates `last_msg_id` configuration value
 to the maximum of the current value and IDs passed to this function.
 Bots which mark messages as seen can rely on this side effect
 to avoid updating `last_msg_id` value manually.

 One #DC_EVENT_MSGS_NOTICED event is emitted per modified chat.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgIds` | `list[uint32]` | ✓ |

### `message_ids_to_search_results`

```
rpc.message_ids_to_search_results(account_id: uint32, message_ids: list[uint32]) → dict[str, MessageSearchResult]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `misc_get_sticker_folder`

```
rpc.misc_get_sticker_folder(account_id: uint32) → str
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `misc_get_stickers`

```
rpc.misc_get_stickers(account_id: uint32) → dict[str, list[str]]
```

for desktop, get stickers from stickers folder,
 grouped by the collection/folder they are in.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `misc_save_sticker`

```
rpc.misc_save_sticker(account_id: uint32, msg_id: uint32, collection: str) → None
```

Saves a sticker to a collection/folder in the account's sticker folder.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |
| `collection` | `str` | ✓ |

### `misc_send_msg`

```
rpc.misc_send_msg(account_id: uint32, chat_id: uint32, text: string | null, file: string | null, filename: string | null, location: array | null, quoted_message_id: integer | null) → tuple[uint32, Message]
```

Send a message to a chat.

 This function returns after the message has been placed in the sending queue.
 This does not imply that the message was really sent out yet.
 However, from your view, you're done with the message.
 Sooner or later it will find its way.

 **Attaching files:**

 Pass the file path in the `file` parameter.
 If `file` is not in the blob directory yet,
 it will be copied into the blob directory.
 If you want, you can delete the file immediately after this function returns.

 You can also write the attachment directly into the blob directory
 and then pass the path as the `file` parameter;
 this will prevent an unnecessary copying of the file.

 In `filename`, you can pass the original name of the file,
 which will then be shown in the UI.
 in this case the current name of `file` on the filesystem will be ignored.

 In order to deduplicate files that contain the same data,
 the file will be named `<hash>.<extension>`, e.g. `ce940175885d7b78f7b7e9f1396611f.jpg`.

 NOTE:
 - This function will rename the file. To get the new file path, call `get_file()`.
 - The file must not be modified after this function was called.
 - Images etc. will NOT be recoded.
   In order to recode images,
   use `misc_set_draft` and pass `Image` as the viewtype.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `text` | `string | null` | ✓ |
| `file` | `string | null` | ✓ |
| `filename` | `string | null` | ✓ |
| `location` | `array | null` | ✓ |
| `quotedMessageId` | `integer | null` | ✓ |

### `misc_send_text_message`

```
rpc.misc_send_text_message(account_id: uint32, chat_id: uint32, text: str) → uint32
```

Returns the messageid of the sent message

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `text` | `str` | ✓ |

### `resend_messages`

```
rpc.resend_messages(account_id: uint32, message_ids: list[uint32]) → None
```

Resend messages and make information available for newly added chat members.
 Resending sends out the original message, however, recipients and webxdc-status may differ.
 Clients that already have the original message can still ignore the resent message as
 they have tracked the state by dedicated updates.

 Some messages cannot be resent, eg. info-messages, drafts, already pending messages or messages that are not sent by SELF.

 message_ids all message IDs that should be resend. All messages must belong to the same chat.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `save_msg_file`

```
rpc.save_msg_file(account_id: uint32, msg_id: uint32, path: str) → None
```

Saves a file copy at the user-provided path.

 Fails if file already exists at the provided path.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |
| `path` | `str` | ✓ |

### `save_msgs`

```
rpc.save_msgs(account_id: uint32, message_ids: list[uint32]) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageIds` | `list[uint32]` | ✓ |

### `search_messages`

```
rpc.search_messages(account_id: uint32, query: str, chat_id: integer | null) → list[uint32]
```

Search messages containing the given query string.
 Searching can be done globally (chat_id=None) or in a specified chat only (chat_id set).

 Global search results are typically displayed using dc_msg_get_summary(), chat
 search results may just highlight the corresponding messages and present a
 prev/next button.

 For the global search, the result is limited to 1000 messages,
 this allows an incremental search done fast.
 So, when getting exactly 1000 messages, the result actually may be truncated;
 the UIs may display sth. like "1000+ messages found" in this case.
 The chat search (if chat_id is set) is not limited.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `query` | `str` | ✓ |
| `chatId` | `integer | null` | ✓ |

### `send_msg`

```
rpc.send_msg(account_id: uint32, chat_id: uint32, data: MessageData) → uint32
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `data` | `MessageData` | ✓ |

### `send_reaction`

```
rpc.send_reaction(account_id: uint32, message_id: uint32, reaction: list[str]) → uint32
```

Send a reaction to message.

 Reaction is a string of emojis separated by spaces. Reaction to a
 single message can be sent multiple times. The last reaction
 received overrides all previously received reactions. It is
 possible to remove all reactions by sending an empty string.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `messageId` | `uint32` | ✓ |
| `reaction` | `list[str]` | ✓ |

### `send_sticker`

```
rpc.send_sticker(account_id: uint32, chat_id: uint32, sticker_path: str) → uint32
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `stickerPath` | `str` | ✓ |

### `wait_next_msgs`

```
rpc.wait_next_msgs(account_id: uint32) → list[uint32]
```

Waits for messages to be processed by the bot and returns their IDs.

 This function is similar to [`get_next_msgs`],
 but waits for internal new message notification before returning.
 New message notification is sent when new message is added to the database,
 on initialization, when I/O is started and when I/O is stopped.
 This allows bots to use `wait_next_msgs` in a loop to process
 old messages after initialization and during the bot runtime.
 To shutdown the bot, stopping I/O can be used to interrupt
 pending or next `wait_next_msgs` call.

 [`get_next_msgs`]: Self::get_next_msgs

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

## Configuration

### `batch_get_config`

```
rpc.batch_get_config(account_id: uint32, keys: list[str]) → dict[str, string | null]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `keys` | `list[str]` | ✓ |

### `batch_set_config`

```
rpc.batch_set_config(account_id: uint32, config: dict[str, string | null]) → None
```

Updates a batch of configuration values.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `config` | `dict[str, string | null]` | ✓ |

### `configure`

```
rpc.configure(account_id: uint32) → None
```

Configures this account with the currently set parameters.
 Setup the credential config before calling this.

 Deprecated as of 2025-02; use `add_transport_from_qr()`
 or `add_or_update_transport()` instead.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_all_ui_config_keys`

```
rpc.get_all_ui_config_keys(account_id: uint32) → list[str]
```

Returns all `ui.*` config keys that were set by the UI.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_config`

```
rpc.get_config(account_id: uint32, key: str) → string | null
```

Returns configuration value for the given key.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `key` | `str` | ✓ |

### `is_configured`

```
rpc.is_configured(account_id: uint32) → bool
```

Checks if the context is already configured.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `set_config`

```
rpc.set_config(account_id: uint32, key: str, value: string | null) → None
```

Sets the given configuration key.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `key` | `str` | ✓ |
| `value` | `string | null` | ✓ |

## Transport

### `add_or_update_transport`

```
rpc.add_or_update_transport(account_id: uint32, param: EnteredLoginParam) → None
```

Configures a new email account using the provided parameters
 and adds it as a transport.

 If the email address is the same as an existing transport,
 then this existing account will be reconfigured instead of a new one being added.

 This function stops and starts IO as needed.

 Usually it will be enough to only set `addr` and `password`,
 and all the other settings will be autoconfigured.

 During configuration, ConfigureProgress events are emitted;
 they indicate a successful configuration as well as errors
 and may be used to create a progress bar.
 This function will return after configuration is finished.

 If configuration is successful,
 the working server parameters will be saved
 and used for connecting to the server.
 The parameters entered by the user will be saved separately
 so that they can be prefilled when the user opens the server-configuration screen again.

 See also:
 - [Self::is_configured()] to check whether there is
   at least one working transport.
 - [Self::add_transport_from_qr()] to add a transport
   from a server encoded in a QR code.
 - [Self::list_transports()] to get a list of all configured transports.
 - [Self::delete_transport()] to remove a transport.
 - [Self::set_transport_unpublished()] to set whether contacts see this transport.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `param` | `EnteredLoginParam` | ✓ |

### `add_transport`

```
rpc.add_transport(account_id: uint32, param: EnteredLoginParam) → None
```

Deprecated 2025-04. Alias for [Self::add_or_update_transport()].

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `param` | `EnteredLoginParam` | ✓ |

### `add_transport_from_qr`

```
rpc.add_transport_from_qr(account_id: uint32, qr: str) → None
```

Adds a new email account as a transport
 using the server encoded in the QR code.
 See [Self::add_or_update_transport].

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qr` | `str` | ✓ |

### `delete_transport`

```
rpc.delete_transport(account_id: uint32, addr: str) → None
```

Removes the transport with the specified email address
 (i.e. [EnteredLoginParam::addr]).

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `addr` | `str` | ✓ |

### `list_transports`

```
rpc.list_transports(account_id: uint32) → list[EnteredLoginParam]
```

Returns the list of all email accounts that are used as a transport in the current profile.
 Use [Self::add_or_update_transport()] to add or change a transport
 and [Self::delete_transport()] to delete a transport.
 Use [Self::list_transports_ex()] to additionally query
 whether the transports are marked as 'unpublished'.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `list_transports_ex`

```
rpc.list_transports_ex(account_id: uint32) → list[TransportListEntry]
```

Returns the list of all email accounts that are used as a transport in the current profile.
 Use [Self::add_or_update_transport()] to add or change a transport
 and [Self::delete_transport()] to delete a transport.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `set_transport_unpublished`

```
rpc.set_transport_unpublished(account_id: uint32, addr: str, unpublished: bool) → None
```

Change whether the transport is unpublished.

 Unpublished transports are not advertised to contacts,
 and self-sent messages are not sent there,
 so that we don't cause extra messages to the corresponding inbox,
 but can still receive messages from contacts who don't know our new transport addresses yet.

 The default is false, but when the user updates from a version that didn't have this flag,
 existing secondary transports are set to unpublished,
 so that an existing transport address doesn't suddenly get spammed with a lot of messages.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `addr` | `str` | ✓ |
| `unpublished` | `bool` | ✓ |

## Backup & import/export

### `export_backup`

```
rpc.export_backup(account_id: uint32, destination: str, passphrase: string | null) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `destination` | `str` | ✓ |
| `passphrase` | `string | null` | ✓ |

### `export_self_keys`

```
rpc.export_self_keys(account_id: uint32, path: str, passphrase: string | null) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `path` | `str` | ✓ |
| `passphrase` | `string | null` | ✓ |

### `get_backup`

```
rpc.get_backup(account_id: uint32, qr_text: str) → None
```

Gets a backup from a remote provider.

 This retrieves the backup from a remote device over the network and imports it into
 the current device.

 Can be canceled by stopping the ongoing process.

 Do not forget to call start_io on the account after a successful import,
 otherwise it will not connect to the email server.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qrText` | `str` | ✓ |

### `get_backup_qr`

```
rpc.get_backup_qr(account_id: uint32) → str
```

Returns the text of the QR code for the running [`CommandApi::provide_backup`].

 This QR code text can be used in [`CommandApi::get_backup`] on a second device to
 retrieve the backup and setup this second device.

 This call will block until the QR code is ready,
 even if there is no concurrent call to [`CommandApi::provide_backup`],
 but will fail after 60 seconds to avoid deadlocks.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_backup_qr_svg`

```
rpc.get_backup_qr_svg(account_id: uint32) → str
```

Returns the rendered QR code for the running [`CommandApi::provide_backup`].

 This QR code can be used in [`CommandApi::get_backup`] on a second device to
 retrieve the backup and setup this second device.

 This call will block until the QR code is ready,
 even if there is no concurrent call to [`CommandApi::provide_backup`],
 but will fail after 60 seconds to avoid deadlocks.

 @deprecated as of 2026-03; use `create_qr_svg(get_backup_qr())` instead.

 Returns the QR code rendered as an SVG image.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `import_backup`

```
rpc.import_backup(account_id: uint32, path: str, passphrase: string | null) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `path` | `str` | ✓ |
| `passphrase` | `string | null` | ✓ |

### `import_self_keys`

```
rpc.import_self_keys(account_id: uint32, path: str, passphrase: string | null) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `path` | `str` | ✓ |
| `passphrase` | `string | null` | ✓ |

### `import_vcard`

```
rpc.import_vcard(account_id: uint32, path: str) → list[uint32]
```

Imports contacts from a vCard file located at the given path.

 Returns the ids of created/modified contacts in the order they appear in the vCard.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `path` | `str` | ✓ |

### `import_vcard_contents`

```
rpc.import_vcard_contents(account_id: uint32, vcard: str) → list[uint32]
```

Imports contacts from a vCard.

 Returns the ids of created/modified contacts in the order they appear in the vCard.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `vcard` | `str` | ✓ |

### `provide_backup`

```
rpc.provide_backup(account_id: uint32) → None
```

Offers a backup for remote devices to retrieve.

 Can be canceled by stopping the ongoing process.  Success or failure can be tracked
 via the `ImexProgress` event which should either reach `1000` for success or `0` for
 failure.

 This **stops IO** while it is running.

 Returns once a remote device has retrieved the backup, or is canceled.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

## Webxdc

### `get_webxdc_blob`

```
rpc.get_webxdc_blob(account_id: uint32, instance_msg_id: uint32, path: str) → str
```

Get blob encoded as base64 from a webxdc message

 path is the path of the file within webxdc archive

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |
| `path` | `str` | ✓ |

### `get_webxdc_href`

```
rpc.get_webxdc_href(account_id: uint32, info_msg_id: uint32) → string | null
```

Get href from a WebxdcInfoMessage which might include a hash holding
 information about a specific position or state in a webxdc app (optional)

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `infoMsgId` | `uint32` | ✓ |

### `get_webxdc_info`

```
rpc.get_webxdc_info(account_id: uint32, instance_msg_id: uint32) → WebxdcMessageInfo
```

Get info from a webxdc message

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |

### `get_webxdc_status_updates`

```
rpc.get_webxdc_status_updates(account_id: uint32, instance_msg_id: uint32, last_known_serial: uint32) → str
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |
| `lastKnownSerial` | `uint32` | ✓ |

### `init_webxdc_integration`

```
rpc.init_webxdc_integration(account_id: uint32, chat_id: integer | null) → integer | null
```

Returns Webxdc instance used for optional integrations.
 UI can open the Webxdc as usual.
 Returns `None` if there is no integration; the caller can add one using `set_webxdc_integration` then.
 `integrate_for` is the chat to get the integration for.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `integer | null` | ✓ |

### `leave_webxdc_realtime`

```
rpc.leave_webxdc_realtime(account_id: uint32, instance_message_id: uint32) → None
```

Leaves the gossip of the webxdc with the given message id.

 NB: When this is called before closing a webxdc app in UIs, it must be guaranteed that
 `send_webxdc_realtime_*()` functions aren't called for the given `instance_message_id`
 anymore until the app is open again.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMessageId` | `uint32` | ✓ |

### `send_webxdc_realtime_advertisement`

```
rpc.send_webxdc_realtime_advertisement(account_id: uint32, instance_msg_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |

### `send_webxdc_realtime_data`

```
rpc.send_webxdc_realtime_data(account_id: uint32, instance_msg_id: uint32, data: list[uint8]) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |
| `data` | `list[uint8]` | ✓ |

### `send_webxdc_status_update`

```
rpc.send_webxdc_status_update(account_id: uint32, instance_msg_id: uint32, update_str: str, descr: string | null) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `instanceMsgId` | `uint32` | ✓ |
| `updateStr` | `str` | ✓ |
| `descr` | `string | null` | ✓ |

### `set_webxdc_integration`

```
rpc.set_webxdc_integration(account_id: uint32, file_path: str) → None
```

Sets Webxdc file as integration.
 `file` is the .xdc to use as Webxdc integration.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `filePath` | `str` | ✓ |

## Locations

### `get_locations`

```
rpc.get_locations(account_id: uint32, chat_id: integer | null, contact_id: integer | null, timestamp_begin: int64, timestamp_end: int64) → list[Location]
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `integer | null` | ✓ |
| `contactId` | `integer | null` | ✓ |
| `timestampBegin` | `int64` | ✓ |
| `timestampEnd` | `int64` | ✓ |

## Provider info

### `get_provider_info`

```
rpc.get_provider_info(account_id: uint32, email: str) → ProviderInfo | None
```

Returns provider for the given domain.

 This function looks up domain in offline database.

 For compatibility, email address can be passed to this function
 instead of the domain.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `email` | `str` | ✓ |

## IO & network

### `accept_incoming_call`

```
rpc.accept_incoming_call(account_id: uint32, msg_id: uint32, accept_call_info: str) → None
```

Accepts an incoming call.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |
| `acceptCallInfo` | `str` | ✓ |

### `call_info`

```
rpc.call_info(account_id: uint32, msg_id: uint32) → CallInfo
```

Returns information about the call.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |

### `end_call`

```
rpc.end_call(account_id: uint32, msg_id: uint32) → None
```

Ends incoming or outgoing call.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |

### `estimate_auto_deletion_count`

```
rpc.estimate_auto_deletion_count(account_id: uint32, from_server: bool, seconds: int64) → uint
```

Estimate the number of messages that will be deleted
 by the set_config()-options `delete_device_after` or `delete_server_after`.
 This is typically used to show the estimated impact to the user
 before actually enabling deletion of old messages.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `fromServer` | `bool` | ✓ |
| `seconds` | `int64` | ✓ |

### `get_migration_error`

```
rpc.get_migration_error(account_id: uint32) → string | null
```

If there was an error while the account was opened
 and migrated to the current version,
 then this function returns it.

 This function is useful because the key-contacts migration could fail due to bugs
 and then the account will not work properly.

 After opening an account, the UI should call this function
 and show the error string if one is returned.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `maybe_network`

```
rpc.maybe_network() → None
```

Indicate that the network likely has come back.
 or just that the network conditions might have changed

### `place_outgoing_call`

```
rpc.place_outgoing_call(account_id: uint32, chat_id: uint32, place_call_info: str, has_video: bool) → uint32
```

Starts an outgoing call.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `placeCallInfo` | `str` | ✓ |
| `hasVideo` | `bool` | ✓ |

### `start_io`

```
rpc.start_io(account_id: uint32) → None
```

Starts background tasks for a single account.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `stop_io`

```
rpc.stop_io(account_id: uint32) → None
```

Stops background tasks for a single account.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

## Events

### `get_next_event`

```
rpc.get_next_event() → Event
```

Get the next event, and remove it from the event queue.

 If no events have happened since the last `get_next_event`
 (i.e. if the event queue is empty), the response will be returned
 only when a new event fires.

 Note that if you are using the `BaseDeltaChat` JavaScript class
 or the `Rpc` Python class, this function will be invoked
 by those classes internally and should not be used manually.

### `get_next_event_batch`

```
rpc.get_next_event_batch() → list[Event]
```

Waits for at least one event and return a batch of events.

## Miscellaneous

### `background_fetch`

```
rpc.background_fetch(timeout_in_seconds: double) → None
```

Performs a background fetch for all accounts in parallel with a timeout.

 The `AccountsBackgroundFetchDone` event is emitted at the end even in case of timeout.
 Process all events until you get this one and you can safely return to the background
 without forgetting to create notifications caused by timing race conditions.

| Param | Type | Required |
|-------|------|----------|
| `timeoutInSeconds` | `double` | ✓ |

### `can_send`

```
rpc.can_send(account_id: uint32, chat_id: uint32) → bool
```

Checks if messages can be sent to a given chat.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `check_email_validity`

```
rpc.check_email_validity(email: str) → bool
```

Checks if an email address is valid.

| Param | Type | Required |
|-------|------|----------|
| `email` | `str` | ✓ |

### `copy_to_blob_dir`

```
rpc.copy_to_blob_dir(account_id: uint32, path: str) → str
```

Copy file to blob dir.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `path` | `str` | ✓ |

### `create_broadcast`

```
rpc.create_broadcast(account_id: uint32, chat_name: str) → uint32
```

Create a new, outgoing **broadcast channel**
 (called "Channel" in the UI).

 Broadcast channels are similar to groups on the sending device,
 however, recipients get the messages in a read-only chat
 and will not see who the other members are.

 Called `broadcast` here rather than `channel`,
 because the word "channel" already appears a lot in the code,
 which would make it hard to grep for it.

 After creation, the chat contains no recipients and is in _unpromoted_ state;
 see [`CommandApi::create_group_chat`] for more information on the unpromoted state.

 Returns the created chat's id.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatName` | `str` | ✓ |

### `create_broadcast_list`

```
rpc.create_broadcast_list(account_id: uint32) → uint32
```

Deprecated 2025-07 in favor of create_broadcast().

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_blob_dir`

```
rpc.get_blob_dir(account_id: uint32) → string | null
```

Get the blob dir.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_connectivity`

```
rpc.get_connectivity(account_id: uint32) → uint32
```

Get the current connectivity, i.e. whether the device is connected to the IMAP server.
 One of:
 - DC_CONNECTIVITY_NOT_CONNECTED (1000-1999): Show e.g. the string "Not connected" or a red dot
 - DC_CONNECTIVITY_CONNECTING (2000-2999): Show e.g. the string "Connecting…" or a yellow dot
 - DC_CONNECTIVITY_WORKING (3000-3999): Show e.g. the string "Getting new messages" or a spinning wheel
 - DC_CONNECTIVITY_CONNECTED (>=4000): Show e.g. the string "Connected" or a green dot

 We don't use exact values but ranges here so that we can split up
 states into multiple states in the future.

 Meant as a rough overview that can be shown
 e.g. in the title of the main screen.

 If the connectivity changes, a #DC_EVENT_CONNECTIVITY_CHANGED will be emitted.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_connectivity_html`

```
rpc.get_connectivity_html(account_id: uint32) → str
```

Get an overview of the current connectivity, and possibly more statistics.
 Meant to give the user more insight about the current status than
 the basic connectivity info returned by get_connectivity(); show this
 e.g., if the user taps on said basic connectivity info.

 If this page changes, a #DC_EVENT_CONNECTIVITY_CHANGED will be emitted.

 This comes as an HTML from the core so that we can easily improve it
 and the improvement instantly reaches all UIs.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_draft`

```
rpc.get_draft(account_id: uint32, chat_id: uint32) → Message | None
```

Get draft for a chat, if any.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `get_http_response`

```
rpc.get_http_response(account_id: uint32, url: str) → HttpResponse
```

Makes an HTTP GET request and returns a response.

 `url` is the HTTP or HTTPS URL.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `url` | `str` | ✓ |

### `get_info`

```
rpc.get_info(account_id: uint32) → dict[str, str]
```

Get system info for an account.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_push_state`

```
rpc.get_push_state(account_id: uint32) → NotifyState
```

Get the current push notification state.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_storage_usage_report_string`

```
rpc.get_storage_usage_report_string(account_id: uint32) → str
```

Get storage usage report as formatted string

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `get_system_info`

```
rpc.get_system_info() → dict[str, str]
```

Returns general system info.

### `ice_servers`

```
rpc.ice_servers(account_id: uint32) → str
```

Returns JSON with ICE servers, to be used for WebRTC video calls.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |

### `leave_group`

```
rpc.leave_group(account_id: uint32, chat_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `misc_send_draft`

```
rpc.misc_send_draft(account_id: uint32, chat_id: uint32) → uint32
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `misc_set_draft`

```
rpc.misc_set_draft(account_id: uint32, chat_id: uint32, text: string | null, file: string | null, filename: string | null, quoted_message_id: integer | null, view_type: Viewtype | None) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |
| `text` | `string | null` | ✓ |
| `file` | `string | null` | ✓ |
| `filename` | `string | null` | ✓ |
| `quotedMessageId` | `integer | null` | ✓ |
| `viewType` | `Viewtype | None` | ✓ |

### `remove_draft`

```
rpc.remove_draft(account_id: uint32, chat_id: uint32) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `chatId` | `uint32` | ✓ |

### `secure_join`

```
rpc.secure_join(account_id: uint32, qr: str) → uint32
```

Continue a Setup-Contact or Verified-Group-Invite protocol
 started on another device with `get_chat_securejoin_qr_code_svg()`.
 This function is typically called when `check_qr()` returns
 type=AskVerifyContact or type=AskVerifyGroup.

 The function returns immediately and the handshake runs in background,
 sending and receiving several messages.
 During the handshake, info messages are added to the chat,
 showing progress, success or errors.

 Subsequent calls of `secure_join()` will abort previous, unfinished handshakes.

 See https://securejoin.delta.chat/ for details about both protocols.

 **qr**: The text of the scanned QR code. Typically, the same string as given
     to `check_qr()`.

 **returns**: The chat ID of the joined chat, the UI may redirect to the this chat.
         A returned chat ID does not guarantee that the chat is protected or the belonging contact is verified.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qr` | `str` | ✓ |

### `secure_join_with_ux_info`

```
rpc.secure_join_with_ux_info(account_id: uint32, qr: str, source: SecurejoinSource | None, uipath: SecurejoinUiPath | None) → uint32
```

Like `secure_join()`, but allows to pass a source and a UI-path.
 You only need this if your UI has an option to send statistics
 to Delta Chat's developers.

 **source**: The source where the QR code came from.
 E.g. a link that was clicked inside or outside Delta Chat,
 the "Paste from Clipboard" action,
 the "Load QR code as image" action,
 or a QR code scan.

 **uipath**: Which UI path did the user use to arrive at the QR code screen.
 If the SecurejoinSource was ExternalLink or InternalLink,
 pass `None` here, because the QR code screen wasn't even opened.
 ```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `qr` | `str` | ✓ |
| `source` | `SecurejoinSource | None` | ✓ |
| `uipath` | `SecurejoinUiPath | None` | ✓ |

### `send_edit_request`

```
rpc.send_edit_request(account_id: uint32, msg_id: uint32, new_text: str) → None
```

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
| `msgId` | `uint32` | ✓ |
| `newText` | `str` | ✓ |

### `set_stock_strings`

```
rpc.set_stock_strings(strings: dict[str, str]) → None
```

| Param | Type | Required |
|-------|------|----------|
| `strings` | `dict[str, str]` | ✓ |

### `sleep`

```
rpc.sleep(delay: double) → None
```

Test function.

| Param | Type | Required |
|-------|------|----------|
| `delay` | `double` | ✓ |

### `stop_background_fetch`

```
rpc.stop_background_fetch() → None
```

### `stop_ongoing_process`

```
rpc.stop_ongoing_process(account_id: uint32) → None
```

Signal an ongoing process to stop.

| Param | Type | Required |
|-------|------|----------|
| `accountId` | `uint32` | ✓ |
