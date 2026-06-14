from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


class UnsafeTargetError(ValueError):
    """Raised when a target URL is outside the local/mock safety boundary."""


DENIED_DOMAINS = {
    "swagbucks.com",
}


def assert_mock_target(url: str) -> None:
    """Allow localhost/private targets and reject public/live survey domains."""

    _assert_url_shape(url)
    hostname = hostname_for(url)
    _assert_not_denied(hostname)

    if is_local_or_private_host(hostname):
        return

    raise UnsafeTargetError(
        "Refusing to run against public hosts. This bot is limited to mock targets."
    )


def assert_target_policy(
    url: str,
    *,
    mode: str = "mock",
    allowed_domains: list[str] | None = None,
    authorization_note: str = "",
) -> None:
    """Validate target URL against mock or explicitly authorized mode."""

    normalized_mode = mode.strip().lower()
    if normalized_mode == "mock":
        assert_mock_target(url)
        return

    if normalized_mode != "authorized":
        raise UnsafeTargetError("target.mode must be either 'mock' or 'authorized'.")

    _assert_url_shape(url)
    hostname = hostname_for(url)
    _assert_not_denied(hostname)

    if not authorization_note.strip():
        raise UnsafeTargetError(
            "Authorized mode requires target.authorization_note to document permission."
        )

    if is_local_or_private_host(hostname):
        return

    if not allowed_domains:
        raise UnsafeTargetError(
            "Authorized mode on public hosts requires target.allowed_domains."
        )

    if not any(_domain_matches(hostname, domain) for domain in allowed_domains):
        raise UnsafeTargetError(
            f"Host '{hostname}' is not listed in target.allowed_domains."
        )


def hostname_for(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower().strip("[]")


def is_local_or_private_host(hostname: str) -> bool:
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        return True

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False

    return address.is_private or address.is_loopback


def _assert_url_shape(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeTargetError("Target URL must use http or https.")

    if not parsed.hostname:
        raise UnsafeTargetError("Target URL must include a host.")


def _assert_not_denied(hostname: str) -> None:
    if any(hostname == domain or hostname.endswith(f".{domain}") for domain in DENIED_DOMAINS):
        raise UnsafeTargetError("Refusing to run against denied live survey domains.")


def _domain_matches(hostname: str, allowed_domain: str) -> bool:
    domain = allowed_domain.lower().strip()
    if not domain:
        return False

    if domain.startswith("*."):
        suffix = domain[2:]
        return hostname.endswith(f".{suffix}") and hostname != suffix

    return hostname == domain
