"""Contract tests for readonly reviewer runtime config in Settings."""

from __future__ import annotations

import os

import pytest

from app.core.config import load_settings


class TestReadonlyReviewerDefaults:
    def test_default_timeout(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        s = load_settings()
        assert s.readonly_reviewer_timeout_seconds == 180

    def test_default_max_output(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        s = load_settings()
        assert s.readonly_reviewer_max_output_bytes == 262144


class TestReadonlyReviewerOverrides:
    def test_timeout_override(self, monkeypatch) -> None:
        monkeypatch.setenv("READONLY_REVIEWER_TIMEOUT_SECONDS", "45")
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        s = load_settings()
        assert s.readonly_reviewer_timeout_seconds == 45

    def test_max_output_override(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.setenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", "8192")
        s = load_settings()
        assert s.readonly_reviewer_max_output_bytes == 8192


class TestReadonlyReviewerInvalidValues:
    def test_timeout_zero_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("READONLY_REVIEWER_TIMEOUT_SECONDS", "0")
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        with pytest.raises(ValueError):
            load_settings()

    def test_timeout_negative_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("READONLY_REVIEWER_TIMEOUT_SECONDS", "-5")
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        with pytest.raises(ValueError):
            load_settings()

    def test_timeout_non_integer_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("READONLY_REVIEWER_TIMEOUT_SECONDS", "abc")
        monkeypatch.delenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", raising=False)
        with pytest.raises(ValueError):
            load_settings()

    def test_max_output_zero_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.setenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", "0")
        with pytest.raises(ValueError):
            load_settings()

    def test_max_output_negative_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.setenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", "-1")
        with pytest.raises(ValueError):
            load_settings()

    def test_max_output_non_integer_raises(self, monkeypatch) -> None:
        monkeypatch.delenv("READONLY_REVIEWER_TIMEOUT_SECONDS", raising=False)
        monkeypatch.setenv("READONLY_REVIEWER_MAX_OUTPUT_BYTES", "xyz")
        with pytest.raises(ValueError):
            load_settings()
