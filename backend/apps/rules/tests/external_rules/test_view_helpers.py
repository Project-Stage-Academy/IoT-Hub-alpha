import pytest

from apps.rules.services.view_helpers import get_json_body


def test_get_json_body_valid_json():
    body = b'{"a": 1, "b": "x"}'
    assert get_json_body(body) == {"a": 1, "b": "x"}


def test_get_json_body_invalid_json_returns_empty_dict():
    body = b'{"a": 1,'
    assert get_json_body(body) == {}


def test_get_json_body_empty_returns_empty_dict():
    assert get_json_body(b"") == {}
