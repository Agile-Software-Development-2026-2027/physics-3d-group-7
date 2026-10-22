# Stop on first error
$ErrorActionPreference = "Stop"

Write-Host "==> Syncing uv dependencies..." -ForegroundColor Cyan
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to sync dependencies with uv."
    exit $LASTEXITCODE
}

Write-Host "==> Installing pre-commit and pre-push hooks..." -ForegroundColor Cyan
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install pre-commit hooks."
    exit $LASTEXITCODE
}

Write-Host "==> Environment and Git hooks configured successfully!" -ForegroundColor Green

