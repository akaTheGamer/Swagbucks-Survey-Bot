from __future__ import annotations

import json

import pytest

from surveybot.config import ConfigLoader
from surveybot.safety import UnsafeTargetError


def write_config(tmp_path, payload):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_config_loader_applies_defaults(tmp_path):
    path = write_config(tmp_path, {"profile": {"age": 41}})

    config = ConfigLoader(path).load()

    assert config.profile.age == 41
    assert config.profile.gender == "female"
    assert config.profile.country == "Germany"
    assert config.profile.language == "German"
    assert config.profile.owns_car is False
    assert config.login.username == "mock_user"
    assert config.automation.min_delay_seconds == 0.5
    assert config.target.base_url == "http://127.0.0.1:8000"
    assert config.target.mode == "mock"
    assert config.target.allowed_domains == []


def test_config_loader_supports_authorized_target_overrides(tmp_path):
    path = write_config(tmp_path, {})

    config = ConfigLoader(path).load(
        base_url_override="https://qa.example.com",
        target_mode_override="authorized",
        allowed_domains_override=["qa.example.com"],
        authorization_note_override="Approved internal QA automation environment.",
    )

    assert config.target.base_url == "https://qa.example.com"
    assert config.target.mode == "authorized"
    assert config.target.allowed_domains == ["qa.example.com"]


def test_config_loader_rejects_invalid_delay_range(tmp_path):
    path = write_config(
        tmp_path,
        {"automation": {"min_delay_seconds": 3, "max_delay_seconds": 0.5}},
    )

    with pytest.raises(ValueError, match="max_delay"):
        ConfigLoader(path).load()


def test_config_loader_rejects_swagbucks_target(tmp_path):
    path = write_config(
        tmp_path,
        {"target": {"base_url": "https://www.swagbucks.com"}},
    )

    with pytest.raises(UnsafeTargetError):
        ConfigLoader(path).load()
