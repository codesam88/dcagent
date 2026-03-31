# Copilot Instructions for dcagent

## Commands

```bash
make test-all          # Full test suite: ruff lint + pytest + pre-commit + online tests
make test              # Offline only: ruff lint + pytest + pre-commit hooks
make format            # Auto-format with ruff
make run               # Start the agent (uv run dcagent serve)
make clean             # Remove build artifacts

uv run ruff check --fix                                         # Lint with auto-fix
uv run pytest                                                   # All unit tests
uv run pytest tests/test_dcagent2.py::test_dispatch_send        # Single test
```

## Architecture

The package lives in `src/dcagent/` and is split into two files:

- **`bot.py`** — CLI argument parsing, account lifecycle commands (`init`, `config`, `link`, `admin`, `join`, `serve`), and a minimal stub `run_bot()` that the event loop calls.
- **`agent.py`** — Overrides `run_bot()` with the full implementation: registers message handlers and starts the pipe listener thread. It is the CLI entry point (`dcagent = "dcagent.agent:main"`).

Two concurrent execution paths run at runtime:

1. **Event loop** — `deltachat2.Bot` dispatches incoming Delta Chat messages to handlers registered as a list of `(handler_fn, event_filter)` tuples. Handler signature: `(bot: Bot, accid: int, event) -> None`.

2. **Pipe listener thread** — Started as a daemon thread if `--pipe PATH` is passed to `serve`. Reads newline-delimited JSON from a Unix named pipe and dispatches to internal command handlers (e.g. `{"cmd": "send", "chat_id": 12, "text": "..."}`).

RPC calls use `deltachat2.Rpc` (a `deltachat2` client). Bot-level configuration is persisted via `rpc.set_config(accid, "ui.<key>", value)` — e.g. `ui.admin_chat` stores the admin group chat ID.

`AgentError` is raised for fatal user-facing errors; it is caught at the top level, logged, and exits with code 1.

## Conventions

- **Private helpers** use a leading underscore: `_dispatch`, `_pipe_listener`, `_ensure_pipe`, `_pipe_send`.
- **Constants** are `UPPER_CASE`; timeout constants are prefixed with underscore: `_JOIN_TIMEOUT`, `_INIT_TIMEOUT`.
- **Section comments** divide source files — `agent.py` uses: `# Pipe listener`, `# Chat handlers`, `# Full run_bot`, `# Entry point`.
- **Ruff** enforces line length 120, pycodestyle errors (`E`), pyflakes (`F`), and isort (`I`).
- **Error handling**: log and continue for pipe I/O errors; `sys.exit(1)` only for fatal setup failures (e.g. SecureJoin timeout, account not configured).

## Testing

Unit tests are in `tests/test_dcagent2.py` using `pytest` with `unittest.mock.MagicMock` for the RPC layer. Integration/online tests (require a live Delta Chat environment) live alongside them and run only via `make test-online`.

After any code change, run `make test-all` before asking for review.

## Agent Rules

- Re-read files before modifying — the user may have changed them.
- Only modify git-tracked files without asking; ask before touching untracked files.
- After tests pass, ask the user to review before committing.
- Check docs for necessary updates after changes.
