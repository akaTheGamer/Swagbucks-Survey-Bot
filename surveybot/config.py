from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .safety import assert_target_policy


@dataclass(frozen=True)
class Profile:
    age: int
    gender: str
    income: str
    interests: list[str] = field(default_factory=list)
    country: str = "Germany"
    language: str = "German"
    owns_car: bool = False


@dataclass(frozen=True)
class Login:
    username: str
    password: str


@dataclass(frozen=True)
class Automation:
    min_delay_seconds: float = 0.5
    max_delay_seconds: float = 3.0


@dataclass(frozen=True)
class Target:
    base_url: str = "http://127.0.0.1:8000"
    mode: str = "mock"
    allowed_domains: list[str] = field(default_factory=list)
    authorization_note: str = ""


@dataclass(frozen=True)
class BotConfig:
    profile: Profile
    login: Login
    automation: Automation = field(default_factory=Automation)
    target: Target = field(default_factory=Target)


class ConfigLoader:
    DEFAULTS: dict[str, Any] = {
        "profile": {
            "age": 34,
            "gender": "female",
            "income": "50000-75000",
            "interests": ["technology", "travel"],
            "country": "Germany",
            "language": "German",
            "owns_car": False,
        },
        "login": {
            "username": "mock_user",
            "password": "mock_password",
        },
        "automation": {
            "min_delay_seconds": 0.5,
            "max_delay_seconds": 3.0,
        },
        "target": {
            "base_url": "http://127.0.0.1:8000",
            "mode": "mock",
            "allowed_domains": [],
            "authorization_note": "",
        },
    }

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(
        self,
        *,
        base_url_override: str | None = None,
        target_mode_override: str | None = None,
        allowed_domains_override: list[str] | None = None,
        authorization_note_override: str | None = None,
    ) -> BotConfig:
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path}")

        with self.path.open("r", encoding="utf-8") as handle:
            raw_config = json.load(handle)

        if not isinstance(raw_config, dict):
            raise ValueError("Config file must contain a JSON object.")

        merged = _deep_merge(deepcopy(self.DEFAULTS), raw_config)
        if base_url_override:
            merged.setdefault("target", {})["base_url"] = base_url_override
        if target_mode_override:
            merged.setdefault("target", {})["mode"] = target_mode_override
        if allowed_domains_override is not None:
            merged.setdefault("target", {})["allowed_domains"] = allowed_domains_override
        if authorization_note_override:
            merged.setdefault("target", {})[
                "authorization_note"
            ] = authorization_note_override

        config = self._to_config(merged)
        self._validate(config)
        return config

    def _to_config(self, data: dict[str, Any]) -> BotConfig:
        profile = data["profile"]
        login = data["login"]
        automation = data["automation"]
        target = data["target"]

        interests = profile.get("interests", [])
        if not isinstance(interests, list):
            raise ValueError("profile.interests must be a list of strings.")

        allowed_domains = target.get("allowed_domains", [])
        if not isinstance(allowed_domains, list):
            raise ValueError("target.allowed_domains must be a list of strings.")

        return BotConfig(
            profile=Profile(
                age=int(profile["age"]),
                gender=str(profile["gender"]).strip(),
                income=str(profile["income"]).strip(),
                interests=[str(item).strip() for item in interests if str(item).strip()],
                country=str(profile.get("country", "Germany")).strip(),
                language=str(profile.get("language", "German")).strip(),
                owns_car=_to_bool(profile.get("owns_car", False)),
            ),
            login=Login(
                username=str(login["username"]),
                password=str(login["password"]),
            ),
            automation=Automation(
                min_delay_seconds=float(automation["min_delay_seconds"]),
                max_delay_seconds=float(automation["max_delay_seconds"]),
            ),
            target=Target(
                base_url=str(target["base_url"]).rstrip("/"),
                mode=str(target.get("mode", "mock")).strip().lower(),
                allowed_domains=[
                    str(domain).strip().lower()
                    for domain in allowed_domains
                    if str(domain).strip()
                ],
                authorization_note=str(target.get("authorization_note", "")).strip(),
            ),
        )

    def _validate(self, config: BotConfig) -> None:
        if config.profile.age <= 0:
            raise ValueError("profile.age must be a positive integer.")

        if not config.profile.gender:
            raise ValueError("profile.gender must not be empty.")

        if not config.profile.income:
            raise ValueError("profile.income must not be empty.")

        if config.automation.min_delay_seconds < 0:
            raise ValueError("automation.min_delay_seconds cannot be negative.")

        if config.automation.max_delay_seconds < config.automation.min_delay_seconds:
            raise ValueError(
                "automation.max_delay_seconds must be greater than or equal to "
                "automation.min_delay_seconds."
            )

        assert_target_policy(
            config.target.base_url,
            mode=config.target.mode,
            allowed_domains=config.target.allowed_domains,
            authorization_note=config.target.authorization_note,
        )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)
