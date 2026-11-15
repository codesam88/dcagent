# Agent Guidelines

## Communication Style

- Stick to facts and established best practice. Do not editorialize or try to be persuasive.
- In assessments and commit messages, reflect uncertainty where it exists. Avoid asserting things as definitive when the evidence is incomplete.
- Skip superlatives and filler ("Clean.", "Perfect.", "This is the right call."). State what happened or what is true and move on.
- Answer questions precisely and avoid jargon. Explain identified problems and conclusions clearly, without extensive prose. Base recommendations on facts and arguments, not convincing language.
- Do not start building from exploratory questions. Present findings and options, then wait for review before implementing.

## Project Orientation

`dcagent` is a lightweight Delta Chat monitoring agent for Linux systems.

| Directory | Stack | Role |
| --------- | ----- | ---- |
| `src/dcagent/` | Python (>=3.12) | Runtime: agent, CLI, heartbeat protocol |
| `tests/` | pytest + bash integration | Unit and integration tests |
| `scripts/` | bash | Helper scripts |
| `examples/` | systemd, GitHub Actions | Deployment examples |
| `docs/` | Markdown | Documentation, including heartbeat protocol |

**Entry points for a new agent:**

- Runtime: `src/dcagent/agent.py`
- CLI: `src/dcagent/bot.py`
- Heartbeat protocol: `src/dcagent/heartbeat.py`
- Unit tests: `tests/test_dcagent.py`
- Integration tests: `tests/integration/`
- Heartbeat docs: `docs/heartbeat.md`
- Dev commands: `make check`, `make test`, `make test-online` (future `justfile`)

## Project Development Workflow

- Before diving into solutions, take a step back and consider best practice, pros and cons of available options. Clarify ambiguous requirements and trade-offs with the user. Verify claims and assumptions based on actual code and tests.
- For non-trivial work, establish a bounded change before editing: the intended outcome, the files or subsystem in scope, and the checks that will establish success. Use `.plan/` when work spans multiple steps.
- Prefer repository mechanisms over agent memory. If a recurring concern cannot be checked by existing commands, tests, or linters, record it as a tooling/backlog item instead of expanding this file.
- Keep implementation, tests, documentation, and generated artifacts aligned in the same change when they describe the same behavior. Do not claim a safeguard exists unless its check is implemented and has run.
- Before claiming success, run the applicable automated checks, inspect the final diff and status, and report any checks or quality gates that remain unavailable.
- When done, provide a summary of the change. When on a feature branch, commit in reasonable steps. Commit messages should include a summary of what changed and why; do not include verbose examples or documentation.
- Update code-level documentation where applicable. Do not include verbose examples or documentation without request.
- Only the user changes files outside the project root. Do not commit or rewrite git history without explicit request.
- Inside the project root, agents may change or delete tracked files; ask before modifying untracked files.
- Files may be edited by the user. If a file was edited manually, re-read it and treat the change as an intended correction; avoid reverting user changes.
- After significant modifications, run `make check`/`make test`. When tests pass, ask the user to review and request changes.
- Prior to commit, consider whether supporting documentation, examples, or scripts still need updates.
- When generating documentation or commit messages, stick to the main points; do not generate detailed examples unless requested; do not duplicate user documentation into code or commit messages.

## Backend tests

- Unit/static checks: `make check` (`uv run ruff check`, `uv run pytest`, pre-commit). Direct commands: `uv run pytest`, `uv run ruff check --fix`.
- Integration tests require a live chatmail server: `make test-online`.
- Tests mock `main.cli` where needed; more advanced tests require a live Delta Chat environment.

## Task Management (.plan)

Tasks live as `.plan/<slug>.md` with YAML frontmatter. The filename (without `.md`) is the unique key. Trivial single-fix tasks skip the plan file.

### Status lifecycle

| status | meaning |
| ------ | ------- |
| `idea` | aspirational — not fully settled, not ready to start |
| `backlog` | accepted but deferred — consider when stepping back to plan |
| `open` | ready to be picked up |
| `in-progress` | actively being worked on |
| `blocked` | cannot proceed; note the blocker in the body |
| `done` | completed |

### Task Management Workflow

- Create new tasks from `.plan/.TEMPLATE.md`.
- Update `status` to match reality; refine problem, goal, and steps in place; append short dated lines for settled decisions.
- Complete: set `status: done`; do not delete the file.
- Block: set `status: blocked` and note the blocker in the body.
- Validate frontmatter against `.plan/.schema.json`.

## Code comments and documentation

- Keep comments concise; state what the code does not already say.
- Describe current state, not progress or plan pointers.
- Code and documentation must be self-contained: describe the current state, never the progress or plans that led to it.
- `.plan/` files are short-lived developer scratchpads; reference them in commit messages only, never in code comments or documentation.
