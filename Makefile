.PHONY: run test test-scripts test-online test-all lint format dist install uninstall docs tags clean help

ARCH := $(shell uname -m)
DIST_PYZ := dist/dcagent-$(ARCH).pyz

# Help
help:
	@echo "dcagent - Makefile targets"
	@echo ""
	@echo "  run              - Start the agent"
	@echo "  check            - Run pre-commit checks, auto-format, linting, unit tests"
	@echo "  format           - Auto-format code (ruff/Black)"
	@echo "  test-online      - Run online integration tests (reset account using 'make clean')"
	@echo "  test             - Run offline/static as well as online tests"
	@echo "  dist             - Build release binary (dist/dcagent-<arch>.pyz)"
	@echo "  install          - Install as a system service (builds dist if needed)"
	@echo "  uninstall        - Remove a previously installed dcagent service"
	@echo "  docs             - Regenerate docs/deltachat-rpc-api.md from installed binary"
	@echo "  tags             - Generate ctags for src/ (ctags)"
	@echo "  clean            - Clean build artifacts"
	@echo "  help             - Show this help message"

# Run the agent
run:
	uv run dcagent serve

# Syntax check all scripts
test-scripts:
	bash -n examples/systemd/setup.sh
	python3 scripts/check-alert-script examples/actions

# Run unit tests and linters
check: test-scripts
	uv run ruff check --fix
	uv run pytest
	pre-commit run --all-files

# Run integration tests against a live chatmail server (runs unit tests first)
test-online:
	pgrep dcagent && (echo "WARNING: dcagent instances running in background" && false) || true
	timeout 80 run-parts tests/integration

# Run all tests
test: check test-online

# Auto-format code
format:
	uv run ruff format

# Build release binary for the current architecture
dist:
	mkdir -p dist
	uv run shiv -c dcagent -o $(DIST_PYZ) .
	@echo
	@echo "Test generated binary:"
	$(DIST_PYZ) -v
	@echo
	@echo "Built done: $(DIST_PYZ)"

$(DIST_PYZ):
	$(MAKE) dist

# Install as a system service
install: $(DIST_PYZ)
	@echo "Install as systemd service. Needs sudo. Will ask to confirm."
	sudo examples/systemd/setup.sh --pyz $(DIST_PYZ)

# Remove a previously installed dcagent service
uninstall:
	@echo "Uninstall systemd service. Needs sudo. Will ask to confirm."
	sudo examples/systemd/setup.sh --uninstall

# Regenerate API reference docs
docs:
	uv run python scripts/gen_rpc_ref.py

# Generate ctags for src/ and tests/
tags:
	ctags -R src/ tests/

# Clean build artifacts
clean:
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/
	find . -type d -name "__pycache__" -delete 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf tests/integration/out/
	rm -rf dist/
