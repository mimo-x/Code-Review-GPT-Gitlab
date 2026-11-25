"""数值型环境变量的解析。"""
import pytest

from core.settings import _env_int


def test_empty_value_uses_the_default(monkeypatch):
    monkeypatch.setenv("REVIEW_MAX_INLINE_COMMENTS", " ")
    assert _env_int("REVIEW_MAX_INLINE_COMMENTS", 20) == 20


def test_number_is_read(monkeypatch):
    monkeypatch.setenv("REVIEW_MAX_INLINE_COMMENTS", "8")
    assert _env_int("REVIEW_MAX_INLINE_COMMENTS", 20) == 8


def test_invalid_value_names_the_variable(monkeypatch):
    monkeypatch.setenv("REVIEW_MAX_INLINE_COMMENTS", "many")
    with pytest.raises(ValueError, match="REVIEW_MAX_INLINE_COMMENTS"):
        _env_int("REVIEW_MAX_INLINE_COMMENTS", 20)
