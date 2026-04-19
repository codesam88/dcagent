# AGENTS.md

Guide for AI agents working with `dcagent`.

Review the README for general intro and usage.

## Development Workflow for Agents

1. Only the user is allowed to change files outside the project root directory.

2. Do not commit changes automatically and never rewrite git history without explicit user request. 

3. Inside the project root directory, Agents can change or delete any files which
   are tracked in git. But ask the user before modifying files not tracked in git.

4. Files may be changed by the user. When edits fail, try to re-read the file
   for possible manual changes. Be careful not to revert such manual changes.

5. After any significant modifications, run tests (`make test`)

6. When tests ran successfully, ask the user to review and request changes.

7. Prior to commit, stop to consider if any supporting documentation,
   examples, scripts may still need to be updated.


## Testing

Tests are implemented using pytest and static linter.
Run basic tests using `make test`. Run all tests using `make test-all`.

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
More advanced tests require a live DeltaChat environment (Docker?)


## References

- [Delta Chat Bot Quickstart](https://bots.delta.chat/quickstart.html)
- [deltabot-cli-py](https://github.com/deltachat-bot/deltabot-cli-py)
- [deltachat2](https://github.com/adbenitez/deltachat2)
- [Echo bot examples](https://github.com/deltachat-bot/echo)
- [JSON-RPC API (Rust)](https://github.com/deltachat/core/blob/main/deltachat-jsonrpc/src/api.rs)
