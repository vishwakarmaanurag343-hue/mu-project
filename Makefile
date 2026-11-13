.PHONY: setup lint test check

setup:
	uv sync
	uv run pre-commit install

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy src

test:
	uv run pytest -m "not live"

check: lint test
	uv run bandit -c pyproject.toml -r src
	uv run pip-audit
