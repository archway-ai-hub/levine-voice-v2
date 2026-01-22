# Quality gates for LiveKit voice agent project
# Usage: make check, make sim, make fix
#
# Prereqs:
#   - uv
#   - uv sync --extra dev

.PHONY: check sim all fix format lint test

all: check sim

# "check" should be deterministic and NOT mutate code
check: format lint test

# Check formatting (no changes)
format:
	uv run ruff format --check .

# Check lint (no changes)
lint:
	uv run ruff check .

# Run tests
test:
	uv run pytest -q

# Auto-fix locally when you want it
fix:
	uv run ruff format .
	uv run ruff check . --fix

# Run golden transcript simulations
sim:
	uv run python scripts/simulate_transcripts.py
