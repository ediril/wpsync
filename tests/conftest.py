import time

import pytest

from wpsync.config import ConfigurationStore


@pytest.fixture(autouse=True)
def local_time_zone(monkeypatch):
    """Dates are written in local time; tests use the fake blog's zone."""
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def store(tmp_path):
    return ConfigurationStore(tmp_path / "home" / "config.json")
