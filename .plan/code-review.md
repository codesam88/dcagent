---
status: open
type: chore
priority: high
area: backend
---

## Notes

Grounding + best-practice review of dcagent (2026-11-15). Records prioritized findings from the discoverer/challenger/verification review; fixes are not yet scheduled. Each item will be addressed one at a time in TDD order after user approval.

HEAD: ha-notifier @ b9f2570 "plan init" (origin/main @ 0056974). Dirty tree: M README.md, M src/dcagent/agent.py (chmod 0620 pipe), M tests/test_dcagent.py (rewrite), ?? examples/home-assistant/, ?? tests/test_ha_bridge.py. No commits made.

### FIX NOW (schedule first)

- CORR-TESTMODE-01 (HIGH) bot.py:428-434 vs agent.py:401-412 — do_serve calls run_bot(rpc, accid, pipe_path, heartbeat, testmode) positionally, but agent.run_bot signature is (rpc, accid, pipe_path, heartbeat_interval, alert_dir, alert_interval, status_dir, status_interval, testmode), so args.testmode lands in alert_dir and testmode stays False; dcmsg never enabled via CLI. Fix call to use kwargs.
- ROB-CONFIG-01 (MEDIUM) bot.py:186-223 — _get_*_chats use unguarded int(x) on config strings; corrupt config raises ValueError. Wrap/validate.
- MISS-HB-SPOOF-01 (MEDIUM) heartbeat.py:111-125 — make_handler trusts parts[1] as addr and marks seen with no sender verification; spoofable. Add origin/author check.
- ROB-PIPE-01 (MEDIUM) agent.py:160-175 — _pipe_listener has no restart/recovery if open() fails or thread dies; add resilient loop + logging.
- CORR-LEAVE-01 (MEDIUM) agent.py:362-375 — _on_leave updates admin/alert lists but ignores heartbeat_chats; remove from heartbeat list too.
- MISS-SECJOIN-01 (MEDIUM) bot.py:244-260 — _securejoin busy-loops get_next_event on the event-loop thread, blocking handlers; move off loop or make async-safe.
- MISS-LOCK-TOCTOU-01 (MEDIUM) bot.py:571-581 + 140-147 — check-then-act lock acquisition race; atomic create with O_EXCL.
- PRAC-TEST-03 + MISS-DOCPROTO-01 (HIGH coverage) tests/integration/* — integration scripts use --listen-socket (not implemented; CLI is --pipe-path), wait for "Heartbeat received from" (code logs "Tick received from"), and "node offline"/"node recovered" casing vs "Node offline"/"Node recovered"; fix tests + docs to match implementation, or implement flags.
- PRAC-SETUP-01 (MEDIUM) examples/systemd/setup.sh:148-149 — actions path resolves to examples/examples/actions (nonexistent); should be $SCRIPTDIR/../actions.
- CORR-ALERT-01 (MEDIUM-LOW) agent.py:60-112 — _handle_alert_state treats category "" as always-send but _pipe_do_alert derives category from args.split; empty category unreachable via pipe; document or allow.

### RIDE-ALONG

- CORR-HB-SEQ-01 heartbeat.py:37 — `self.seq + 1 % 1000` precedence leaves modulo ineffective; should be `(self.seq + 1) % 1000`.
- SEC-PIPE-01 (LOW) agent.py:43-44 — pipe created with default mode before chmod; tighten creation mode.
- SEC-PIPE-02 — chmod 0620 already in working tree (agent.py) pending commit.
- SEC-CHAT-01 (INFO) — by design; no change.
- PRAC-META-01 — pyproject description placeholder "Add your description here".
- PRAC-LINT-01 agent.py:196 — log.warn deprecated; use log.warning.
- MISS-SELFREENTRY-01 — outgoing re-entry handling gap.
- MISS-IMPORT-SIG-01 bot.py:82 — signal.signal at import time; guard for non-main threads.

### CONVENTION-GAP

- PRAC-DOC-01 — .github/copilot-instructions.md stale (references test_dcagent2.py, link/join commands, JSON pipe protocol) vs actual tests/test_dcagent.py and --pipe-path; refresh.
- Literal `1` used for self contact id (agent.py:375) instead of SpecialContactId.SELF where available.

### STRUCK

- ROB-LEAVE-01 (REJECT) — hardcoding self contact id 1 is acceptable for deltachat core; not a bug.

### Next step

Await user approval before scheduling fixes; implement one item per worker with TDD (failing test first, then fix). Do not commit.


## Appendix 2026-11-15 — Detailed findings (appended, history preserved)

### FIX NOW

#### CORR-TESTMODE-01 — HIGH — bot.py:423-434 vs agent.py:401-436

- **Problem/criticism**: `do_serve` calls `run_bot(rpc, accid, args.pipe_path, args.heartbeat, args.testmode)` positionally, but `agent.run_bot` is `(rpc, accid, pipe_path, heartbeat_interval, alert_dir, alert_interval, status_dir, status_interval, testmode)`. `args.testmode` therefore binds to `alert_dir`, and `testmode` keeps its default `False`; `dcmsg` stays disabled and `_testmode` never becomes True. Observable: `serve --testmode` still logs "dcmsg command requires --testmode".
- **Why it matters**: Test mode is silently dead in production; integration script 04 exercises `dcmsg` and would fail; also `alert_dir` receives a `bool`, a latent type error if that parameter is ever consumed.
- **How to address**: Call with keyword arguments: `run_bot(rpc, accid, pipe_path=args.pipe_path, heartbeat_interval=args.heartbeat, testmode=args.testmode)`. Verification: unit test patching `dcagent.bot.run_bot` and asserting `called_kwargs["testmode"] is True` and `alert_dir == ""`; run `uv run pytest tests/test_dcagent.py -k testmode`.
- **Falsifier**: Would be disproved if a trace shows `_testmode is True` after `serve --testmode` under the current positional call; under the present signature that cannot happen.

#### ROB-CONFIG-01 — MEDIUM — bot.py:186-224 (`_get_*_chats`)

- **Problem/criticism**: `_get_admin_chats`, `_get_alert_chats`, `_get_heartbeat_chats` do `[int(x) for x in raw.split(",") if x.strip()]` with no validation. A corrupt/typo config value (e.g. `"5,abc"`) raises `ValueError`. Worse, deltachat2 swallows exceptions raised inside sync event handlers (`client.py:104-108`) and a dead heartbeat sender thread leaves the process alive but silent.
- **Why it matters**: One bad config string can crash startup or kill handlers invisibly; operator sees a "running" bot with no heartbeats/alerts.
- **How to address**: Add a safe parser helper that skips unparseable tokens, logs a warning with the offending value and key, and returns the valid subset; optionally validate on startup. Verification: unit test `_get_alert_chats` with `"5,abc,7"` returns `[5, 7]` and logs warning; property test with random strings never raises.
- **Falsifier**: Disproved if corrupt config consistently raises and is caught/logged without process death; current code raises uncaught in handler context.

#### MISS-HB-SPOOF-01 — MEDIUM — heartbeat.py:104-125 (`make_handler`)

- **Problem/criticism**: `make_handler` parses `parts = (msg.text or "").split()`, takes `addr = parts[1]`, and calls `_mark_seen(addr)` without verifying the sender is the claimed address. Any heartbeat-group member can broadcast `tick victim@example.com 1` and keep `victim` marked alive indefinitely, suppressing offline alerts.
- **Why it matters**: Liveness monitoring is security-relevant; a malicious or compromised member can mask a node outage (false "alive").
- **How to address**: Derive/verify the sender identity from the message (`msg.from_id` / `get_contact`) and only mark seen when the claimed `addr` matches the sender's address; reject/log mismatches. Verification: unit test feeding a message whose text claims addr A but whose from_id resolves to B asserts `_mark_seen` not called for A and a warning logged.
- **Falsifier**: Disproved if Delta Chat guarantees sender authenticity of text such that spoofing is impossible; the current handler still trusts text, so evidence stands.

#### ROB-PIPE-01 — MEDIUM — agent.py:160-175 (`_pipe_listener`)

- **Problem/criticism**: `_ensure_pipe` runs once; `open(path)` happens once per writer cycle but if the FIFO is deleted, `open` raises `FileNotFoundError` and kills the daemon thread (stderr only, invisible under `--log-file`'s default handler setup); startup `EACCES` on `mkfifo` leaves the bot pipe-less with no retry; an empty FIFO can spin busy. No restart/backoff/logging.
- **Why it matters**: External alert/status integration silently stops; operators may not notice until alerts are missed.
- **How to address**: Wrap `_ensure_pipe`+open+read in an outer loop with backoff (e.g. 1-5s), log exceptions at warning/error, recreate FIFO on `FileNotFoundError`, and avoid busy-spin on EOF (existing `for line in pipe` already blocks; keep). Verification: unit test monkeypatching `open` to raise once then succeed asserts thread stays alive and logs; integration FIFO delete/recreate test.
- **Falsifier**: Disproved if deletion of the FIFO during operation is automatically recovered by the current single loop; it is not, because the exception exits `_pipe_listener`.

#### CORR-LEAVE-01 — MEDIUM — agent.py:342-375 (`_on_leave`)

- **Problem/criticism**: Removes the chat from `ui.admin_chats` and `ui.alert_chats` but not `ui.heartbeat_chats`. A removed heartbeat chat keeps sending/receiving heartbeats; additionally, if `_get_heartbeat_chats` returns stale entries, handlers spam `JsonRpcError` per interval. Observable: `/leave <heartbeat_chat_id>` leaves the chat in Delta Chat but config still lists it.
- **Why it matters**: Ghost heartbeat channels cause false liveness data and repeated RPC errors.
- **How to address**: Also prune `ui.heartbeat_chats` when `chat_id` present, mirroring admin/alert handling. Verification: unit test `_on_leave` with heartbeat chat present asserts `set_config` called for `ui.heartbeat_chats` without that id; grep for heartbeat_chats in `_on_leave`.
- **Falsifier**: Disproved if heartbeat chats are intentionally immortal/non-removable; README/docs do not state that, and `/leave` claims generic leave.

#### MISS-SECJOIN-01 — MEDIUM — bot.py:244-260 (`_securejoin`)

- **Problem/criticism**: `_securejoin` busy-loops `rpc.get_next_event()` for up to 60s on the same thread that runs sync command handlers (and, in `do_admin/do_alert/do_heartbeat`, the CLI thread). In `serve`, SecureJoin is triggered via chat commands on the event-loop thread, so the loop blocks and drops `INCOMING_MSG`/tick events, causing false offline detection.
- **Why it matters**: Joining a chat during operation can make the bot appear offline and miss messages.
- **How to address**: Move the wait loop off the event loop (background thread + `threading.Event`/result queue) or make it async-safe; keep `_JOIN_TIMEOUT`. Verification: integration test joining while heartbeats flow shows no "Node offline" false positive; unit test `_securejoin` returns chat_id when progress event arrives.
- **Falsifier**: Disproved if deltachat2 handlers are reentrant/async and `get_next_event` does not block the loop; current sync hook behavior says otherwise.

#### MISS-LOCK-TOCTOU-01 — MEDIUM — bot.py:120-150 (`_check_dcagent_lock`/`_write_dcagent_lock`) + 571-581

- **Problem/criticism**: Lock acquisition is check-then-act: `_check_dcagent_lock` reads PID then `_write_dcagent_lock` opens with `"w"` (truncate). Two processes starting together can both see no/stale lock and both write, double-running the same account (duplicate heartbeats/alerts). Also `_write_dcagent_lock` swallows `OSError`.
- **Why it matters**: Duplicate bot processes corrupt liveness/alerting and can race on Delta Chat account DB.
- **How to address**: Atomic create with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)` writing PID; treat `FileExistsError` as locked; validate stale PID and unlink+retry with care. Verification: concurrency test launching two `do_serve`/lock acquisitions asserts one fails "Could not acquire lock"; grep for `O_EXCL`.
- **Falsifier**: Disproved if filesystem `open(...,"w")` is atomic across processes; it is not.

#### PRAC-TEST-03 + MISS-DOCPROTO-01 — HIGH coverage — tests/integration/02..06, docs/heartbeat.md

- **Problem/criticism**: Integration scripts use `--listen-socket`/`nc -U` but CLI only implements `--pipe-path` with a FIFO (fire-and-forget writes, no `quit`/`ok`); they wait for `"Heartbeat received from"` while code logs `"Tick received from"`; they match `"node offline"`/`"node recovered"` but code/alerts use `"Node offline"`/`"Node recovered"` (and alert text `"⚠️ Node offline:"`); docs/heartbeat.md says message format `heartbeat <addr> <seq>` while code sends `tick ...`; timeout env naming mismatch.
- **Why it matters**: Integration suite cannot pass as written; docs mislead operators and test authors.
- **How to address**: Either implement `--listen-socket` TCP/Unix socket protocol with `quit`/`ok`, or rewrite scripts to FIFO writes (`printf '...\n' > "$pipe"`), update waits to `"Tick received from"`, `"Node offline"`, `"Node recovered"`, and align docs to `tick`. Verification: `make test-online` green on a live env; `grep` for stale tokens returns none.
- **Falsifier**: Disproved if `--listen-socket` exists somewhere; `_build_parser` shows it does not.

#### PRAC-SETUP-01 — MEDIUM — examples/systemd/setup.sh:148-149

- **Problem/criticism**: Copies example actions from `"$SCRIPTDIR/../examples/actions"`, but script lives in `examples/systemd`, so that resolves to `examples/examples/actions` (nonexistent). Correct path is `"$SCRIPTDIR/../actions"` (i.e. `examples/actions`). `make test-scripts` only runs `bash -n`, which cannot catch a nonexistent directory guarded by `[[ -d ... ]]`.
- **Why it matters**: Example action scripts are never installed; cron/action integration silently incomplete.
- **How to address**: Change to `"$SCRIPTDIR/../actions"`; strengthen script test to run with a temp root or assert source dir exists. Verification: `bash -n` plus a dry-run/install test checking `$DCAGENT_CONF_DIR/actions` populated; `grep -R "examples/examples/actions"` returns none.
- **Falsifier**: Disproved if `examples/examples/actions` exists; tree shows `examples/actions`.

#### CORR-ALERT-01 — MEDIUM-LOW — agent.py:60-112 (`_handle_alert_state`)

- **Problem/criticism**: `_handle_alert_state` treats `category == ""` as always-send bypassing dedup, but `_pipe_do_alert` derives `category = parts[0]` from `args.split(None, 1)` and rejects empty args, so an empty category is unreachable via the pipe. The docstring in bot.py and tests encode the fiction. Either allow empty category or remove the branch and update docs/tests.
- **Why it matters**: Dead branch + misleading documentation; tests assert behavior that production cannot trigger.
- **How to address**: Decide policy: if "always send" is desired, allow `alert` with no category (or a sentinel like `*`); otherwise delete the `category == ""` branch and update `test_handle_alert_state_immediate_category` and docs. Verification: grep for `category == ""` and updated tests; `uv run pytest tests/test_dcagent.py -k handle_alert_state`.
- **Falsifier**: Disproved if a pipe invocation can produce empty category under current parsing; `parts[0]` on non-empty args is never `""`.

### RIDE-ALONG

#### CORR-HB-SEQ-01 — heartbeat.py:37 (`_next_seq`)

- **Problem/criticism**: `self.seq = self.seq + 1 % 1000` parses as `self.seq + (1 % 1000)` = `self.seq + 1`; modulo never wraps. Spec says monotonic, so harmless, but intent was `(self.seq + 1) % 1000`.
- **Why it matters**: Minor correctness/clarity; seq grows unbounded (still fine for Python int).
- **How to address**: Use `(self.seq + 1) % 1000` or remove modulo entirely and document monotonic. Verification: unit test `_next_seq` wraps 999->0 if modulo retained; grep.
- **Falsifier**: Disproved if spec requires unbounded monotonic; then remove modulo and update.

#### SEC-PIPE-01 — LOW — agent.py:36-55 (`_ensure_pipe`)

- **Problem/criticism**: FIFO is created with default mode then chmod'd to 0620; window exists where mode may be broader; also TOCTOU between `os.path.exists`/`os.stat`/`os.remove`/`os.mkfifo`.
- **Why it matters**: Brief broader permissions and race on path replacement.
- **How to address**: Create with `os.mkfifo(path, 0o620)` (mode masked by umask) and chmod after; document TOCTOU as accepted or use `O_CREAT|O_EXCL` equivalent. Verification: test mode bits after creation; no regression.
- **Falsifier**: Disproved if `mkfifo` mode argument is ignored by umask such that chmod still required; then keep chmod and note.

#### SEC-PIPE-02 — LOW — agent.py:49-55 (chmod 0620)

- **Problem/criticism**: chmod 0620 change is in working tree but uncommitted.
- **Why it matters**: Permission hardening pending review/commit.
- **How to address**: Review and commit as part of permission group; no code change. Verification: `git diff` shows only chmod; `stat -c %a pipe` is 620.
- **Falsifier**: N/A (process item).

#### SEC-CHAT-01 — INFO — agent.py:186-196 (`_on_new_message`)

- **Problem/criticism**: `_on_new_message` gates unknown chats but `/help`, `/ping`, `/version` are not gated by chat membership (by design; README only star-gates? Actually admin commands gate). 
- **Why it matters**: Informational; help/ping/version readable by any chat the bot is in. Intended.
- **How to address**: No change; document intended exposure. Verification: tests unchanged.
- **Falsifier**: If policy requires gating, add membership checks to those handlers.

#### PRAC-META-01 — pyproject.toml:4

- **Problem/criticism**: `description = "Add your description here"` placeholder.
- **Why it matters**: Package metadata unprofessional; tooling/readme generation.
- **How to address**: Set real description. Verification: `uv build` metadata; grep placeholder none.
- **Falsifier**: N/A.

#### PRAC-LINT-01 — agent.py:196 (`log.warn`)

- **Problem/criticism**: Uses deprecated `log.warn` (alias) instead of `log.warning`; ruff E/F/I cannot flag deprecation. Verified DeprecationWarning.
- **Why it matters**: Deprecated API; future removal.
- **How to address**: Replace `log.warn` with `log.warning`. Verification: grep `log.warn(` none; `uv run ruff check`.
- **Falsifier**: Disproved if `logging.Logger.warn` is not deprecated in target Python; it is.

#### MISS-SELFREENTRY-01 — LOW — agent.py handlers

- **Problem/criticism**: Outgoing `SELF` messages re-enter hooks; no `is_outgoing=False` guard; in testmode `dcmsg` only.
- **Why it matters**: Self-messages can trigger handlers unexpectedly.
- **How to address**: Add `is_outgoing=False` to `events.NewMessage(...)` hooks where appropriate. Verification: test self-message not handled.
- **Falsifier**: If deltachat2 never delivers own messages to hooks, no change needed; current code lacks guard.

#### MISS-IMPORT-SIG-01 — LOW — bot.py:82

- **Problem/criticism**: `signal.signal(signal.SIGTERM, _sigterm_handler)` runs at import time; if module imported off main thread, raises `ValueError`.
- **Why it matters**: Importing dcagent from non-main contexts (tests, plugins) can fail.
- **How to address**: Move registration into `main()` or guard with `threading.current_thread() is threading.main_thread()`. Verification: import in worker thread succeeds.
- **Falsifier**: Disproved if all imports occur on main thread in practice; tests may import off-thread.

### CONVENTION-GAP

#### PRAC-DOC-01 — .github/copilot-instructions.md

- **Problem/criticism**: Stale: references `tests/test_dcagent2.py`, `link`/`join` commands, JSON pipe protocol; actual is `tests/test_dcagent.py`, `admin`/`alert`/`heartbeat`, `--pipe-path` FIFO.
- **Why it matters**: Misguides agents/contributors.
- **How to address**: Refresh docs to actual commands/tests/protocol.
- **Falsifier**: N/A.

#### Literal `1` for self contact id — agent.py:375

- **Problem/criticism**: Uses literal `1` instead of `SpecialContactId.SELF` where available.
- **Why it matters**: Readability/maintainability; canonical constant clearer.
- **How to address**: Use constant if exported by deltachat2; keep `1` fallback. STRUCK ROB-LEAVE-01 says hardcoding acceptable.
- **Falsifier**: If deltachat2 doesn't expose constant, keep literal.

### STRUCK

#### ROB-LEAVE-01 — REJECT

- **Decision**: Hardcoding self contact id `1` is acceptable for deltachat core; not a bug. No change.
