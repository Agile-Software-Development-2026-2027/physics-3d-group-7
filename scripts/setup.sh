#!/usr/bin/env bash
set -euo pipefail

echo "==> Syncing uv dependencies..."
uv sync

echo "==> Installing pre-commit and pre-push hooks..."
uv run pre-commit install --hook-type pre-commit --hook-type pre-push

echo "==> Environment and Git hooks configured successfully!"

