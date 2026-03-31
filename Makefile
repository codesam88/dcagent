.PHONY: run test test-online test-all lint format clean help

# Help
help:
	@echo "dcagent - Makefile targets"
	@echo ""
	@echo "  run              - Start the agent"
	@echo "  test             - Run unit tests and linters"
	@echo "  test-online      - Run unit tests then integration tests (requires network)"
	@echo "  test-all         - Alias for test-online"
	@echo "  format           - Format code"
	@echo "  clean            - Clean build artifacts"
	@echo "  help             - Show this help message"

# Run the agent
run:
	uv run dcagent serve

# Run unit tests and linters
test:
	uv run ruff check
	uv run pytest
	pre-commit run --all-files

# Run integration tests against a live chatmail server (runs unit tests first)
test-online:
	run-parts tests/

# Run all tests
test-all: test test-online

# Auto-format code
format:
	uv run ruff format

# Clean build artifacts
clean:
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete 2>/dev/null || true
