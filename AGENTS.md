# AGENTS.md

Guide for AI agents working with `dcagent`.

Review the README for general intro and usage.

## Agent Instructions

1. Only the user is allowed to change files outside the project root directory.

2. Inside the project root directory, Agents can change or delete any files which
   are tracked in git. But ask the user before modifying files not tracked in git.

2. Before working on files, re-read them in case they were changed by the user.

3. After any modification, always run tests (`make test`)

4. Once tests are successful, run the code-formatter and ask the user for review.

5. Once the user is happy or about to commit, review the documentation for nay
   necessary updates.

### Make Commands Reference

| Command | Purpose |
|---------|---------|
| `make run` | Start the agent |
| `make test` | Run all tests (linter + pytest) |
| `make format` | Format code with ruff |
| `make clean` | Remove build/cache artifacts |
| `make help` | Show all targets |

## Testing

Tests are implemented using pytest and static linker.
Run all tests using `make test`.

Or run specific tests using respective commands:

```bash
# Run ruff linter (with auto-fix):
uv run ruff check --fix

# Run all pytest tests
uv run pytest

# Run a specific pytest test
uv run pytest test_dcagent.py::test_dispatch_routing
```

Tests are pretty basic right now, mocking `main.cli` where needed.
When adding tests, follow this pattern for isolation:

```python
import main

original_cli = main.cli
main.cli = MockCli()
try:
    # exercise the function under test
finally:
    main.cli = original_cli
```

More advanced tests require a live DeltaChat environment (Docker?)


## References

- [Delta Chat Bot Quickstart](https://bots.delta.chat/quickstart.html)
- [deltabot-cli-py](https://github.com/deltachat-bot/deltabot-cli-py)
- [deltachat2](https://github.com/adbenitez/deltachat2)
- [Echo bot examples](https://github.com/deltachat-bot/echo)
- [JSON-RPC API (Rust)](https://github.com/deltachat/core/blob/main/deltachat-jsonrpc/src/api.rs)
