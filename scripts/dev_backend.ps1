$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$env:PYTHONPATH = "$root;$backend"
Set-Location $backend
alembic upgrade head
python -m uvicorn app.main:app --reload
