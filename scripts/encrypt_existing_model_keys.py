from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.secrets import encrypt_secret, is_encrypted_secret  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import ModelProvider  # noqa: E402


def main() -> None:
    changed = 0
    with SessionLocal() as db:
        providers = db.query(ModelProvider).all()
        for provider in providers:
            for field in ("api_key", "embedding_api_key"):
                value = getattr(provider, field)
                if value and not is_encrypted_secret(value):
                    setattr(provider, field, encrypt_secret(value))
                    changed += 1
            db.add(provider)
        db.commit()
    print(f"Encrypted {changed} model provider secret field(s).")


if __name__ == "__main__":
    main()
