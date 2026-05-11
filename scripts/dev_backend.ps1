$env:PYTHONPATH = "E:\reviewer;E:\reviewer\backend"
python -m uvicorn app.main:app --reload --app-dir E:\reviewer\backend
