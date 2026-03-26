import os

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test by removing CE_* env vars."""
    for key in list(os.environ):
        if key.startswith("CE_"):
            monkeypatch.delenv(key, raising=False)
