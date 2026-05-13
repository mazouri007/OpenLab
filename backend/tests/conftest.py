from __future__ import annotations

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TEST_DIR = Path(tempfile.mkdtemp(prefix="openlab-tests-"))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DIR / 'test.db'}")
os.environ.setdefault("APP_SECRET_KEYS", "K7T1ua7IshX1OPP9cqajFI7cdqfRgYT-DCQY2TRTwWY=")
os.environ.setdefault("CHROMA_PERSIST_DIRECTORY", str(TEST_DIR / "chroma"))
os.environ.setdefault("ENABLE_MOCK_LLM", "true")

config = Config(str(BACKEND / "alembic.ini"))
config.set_main_option("script_location", str(BACKEND / "alembic"))
command.upgrade(config, "head")
