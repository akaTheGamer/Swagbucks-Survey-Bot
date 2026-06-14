from __future__ import annotations

import pytest

from surveybot.safety import UnsafeTargetError, assert_mock_target, assert_target_policy


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://192.168.1.10:8000",
        "http://10.0.0.5:8000",
    ],
)
def test_allows_local_and_private_targets(url):
    assert_mock_target(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.swagbucks.com",
        "https://surveys.swagbucks.com",
        "https://example.com",
    ],
)
def test_rejects_public_or_live_survey_targets(url):
    with pytest.raises(UnsafeTargetError):
        assert_mock_target(url)


def test_authorized_mode_allows_allowlisted_public_domain():
    assert_target_policy(
        "https://qa.example.com/surveys",
        mode="authorized",
        allowed_domains=["qa.example.com"],
        authorization_note="Approved internal QA automation environment.",
    )


def test_authorized_mode_requires_allowlist_for_public_domain():
    with pytest.raises(UnsafeTargetError, match="allowed_domains"):
        assert_target_policy(
            "https://qa.example.com/surveys",
            mode="authorized",
            allowed_domains=[],
            authorization_note="Approved internal QA automation environment.",
        )


def test_authorized_mode_requires_authorization_note():
    with pytest.raises(UnsafeTargetError, match="authorization_note"):
        assert_target_policy(
            "https://qa.example.com/surveys",
            mode="authorized",
            allowed_domains=["qa.example.com"],
            authorization_note="",
        )


def test_authorized_mode_still_rejects_denied_domains():
    with pytest.raises(UnsafeTargetError):
        assert_target_policy(
            "https://www.swagbucks.com",
            mode="authorized",
            allowed_domains=["www.swagbucks.com"],
            authorization_note="This should still be blocked.",
        )
