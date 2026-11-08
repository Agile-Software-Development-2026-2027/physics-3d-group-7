.PHONY: setup test lint format check pre-commit pre-push

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

pre-commit:
	uv run pre-commit run --all-files

pre-push:
	uv run pre-commit run --hook-stage pre-push --all-files

gui:
	uv run apkit4d gui

cli:
	uv run apkit4d

check: lint test

