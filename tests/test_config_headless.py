"""
config.HEADLESS is read once at import time, so these tests force a fresh
import under each env var value rather than just checking the already-imported
module (which would just reflect whatever the test process happened to start
with).
"""

import importlib
import sys


def _reload_config_with_env(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("HEADLESS", raising=False)
    else:
        monkeypatch.setenv("HEADLESS", value)
    sys.modules.pop("config", None)
    return importlib.import_module("config")


def test_headless_defaults_to_false_when_unset(monkeypatch):
    config = _reload_config_with_env(monkeypatch, None)
    assert config.HEADLESS is False


def test_headless_true_from_env(monkeypatch):
    config = _reload_config_with_env(monkeypatch, "true")
    assert config.HEADLESS is True


def test_headless_accepts_1_and_yes(monkeypatch):
    assert _reload_config_with_env(monkeypatch, "1").HEADLESS is True
    assert _reload_config_with_env(monkeypatch, "yes").HEADLESS is True


def test_headless_false_variants(monkeypatch):
    assert _reload_config_with_env(monkeypatch, "false").HEADLESS is False
    assert _reload_config_with_env(monkeypatch, "0").HEADLESS is False
    assert _reload_config_with_env(monkeypatch, "").HEADLESS is False
