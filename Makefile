.PHONY: run test lint format clean help

# Help
help:
	@echo "dcagent - Makefile targets"
	@echo ""
	@echo "  run       - Start the agent"
	@echo "  test      - Run all tests"
	@echo "  format    - Format code"
	@echo "  clean     - Clean build artifacts"
	@echo "  help      - Show this help message"

# Run the agent
run:
	uv run dcagent serve

# Run all tests
test:
	uv run ruff check
	uv run pytest
	pre-commit run --all-files

# Auto-format code
format:
	uv run ruff format

# Clean build artifacts
clean:
	rm -rf .ruff_cache/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	find . -name "*.pyc" -delete 2>/dev/null || true
