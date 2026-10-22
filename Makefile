.PHONY: setup test lint format check

setup:
	uv sync
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

test:
	uv run pytest

lint:
	uv run ruff check --fix
	uv run ty check

format:
	uv run ruff format

check: lint test

