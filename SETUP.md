## Development Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for package and environment management and `pre-commit` for code quality checks (Ruff, Ty, Pytest).

### 1. Prerequisites

Ensure `uv` is installed on your system. If not installed:

- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  or
  ```powershell
  winget install --id=astral-sh.uv -e
  ```
- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **python (not reccomended):**
  ```
  pip install uv
  ```
If you feel brave you can check how to install uv from: https://docs.astral.sh/uv/getting-started/installation/

### 2. Initial Setup

After cloning the repository, run the setup script to synchronize virtual environment dependencies and register Git pre-commit & pre-push hooks:

- **Windows (PowerShell):**
  ```powershell
  .\scripts\setup.ps1
  ```
- **macOS / Linux:**
  ```bash
  ./scripts/setup.sh
  ```
  _(or `make setup` if `make` is installed)_

### 3. Development Commands

| Action              | Command                             | Makefile (if available) |
| :------------------ | :---------------------------------- | :---------------------- |
| **Run tests**       | `uv run pytest`                     | `make test`             |
| **Run type checks** | `uv run ty check`                   | `make lint`             |
| **Run linter**      | `uv run ruff check --fix`           | `make lint`             |
| **Format code**     | `uv run ruff format`                | `make format`           |
| **Run all checks**  | `uv run pre-commit run --all-files` | `make check`            |
