.PHONY: setup lint test check api web

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

api:
	uv run uvicorn alphalens.api.main:app --reload --host 127.0.0.1 --port 8000

web:
	cd frontend && npm run dev

demo:
	uv run python scripts/download_prices.py
	uv run python scripts/build_dataset.py
	uv run python scripts/run_backtest.py
	uv run python scripts/precompute.py
	uv run uvicorn alphalens.api.main:app --host 127.0.0.1 --port 8000

