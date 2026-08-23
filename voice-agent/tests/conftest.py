"""Shared test setup: every test gets its own empty data directory."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the global store at a throwaway folder so tests never touch data/."""
    from assistant import store as store_module

    fresh = store_module.Store(tmp_path)
    monkeypatch.setattr(store_module, "store", fresh)

    import assistant.tools as tools_module
    import assistant.telephony as telephony_module

    monkeypatch.setattr(tools_module, "store", fresh)
    monkeypatch.setattr(telephony_module, "store", fresh)
    return fresh
