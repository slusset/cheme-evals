"""
Tests for provider utilities — the pure parts.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers import resolve_provider, PROVIDERS, DEFAULT_PROVIDER


class TestResolveProvider:

    def test_none_returns_default(self):
        assert resolve_provider(None) == DEFAULT_PROVIDER

    def test_valid_provider_returned(self):
        for name in PROVIDERS:
            assert resolve_provider(name) == name

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            resolve_provider("nonexistent_provider")

    def test_error_lists_available(self):
        with pytest.raises(ValueError, match="anthropic"):
            resolve_provider("bad")
