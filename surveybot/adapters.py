from __future__ import annotations

from .config import BotConfig
from .safety import UnsafeTargetError, assert_target_policy


class DataAttributeSurveyAdapter:
    """Adapter for sites that expose the surveybot data-testid contract."""

    consent_values = {"allowed", "qa", "training", "test"}

    async def assert_target_allowed(self, page, config: BotConfig) -> None:
        assert_target_policy(
            page.url,
            mode=config.target.mode,
            allowed_domains=config.target.allowed_domains,
            authorization_note=config.target.authorization_note,
        )

        if config.target.mode != "authorized":
            return

        if await self._page_declares_consent(page):
            return

        raise UnsafeTargetError(
            "Authorized real-domain runs require the page to declare consent with "
            "<meta name='surveybot-automation' content='allowed'> or "
            "<html data-surveybot-automation='allowed'>."
        )

    async def _page_declares_consent(self, page) -> bool:
        meta = page.locator("meta[name='surveybot-automation']").first
        if await meta.count():
            content = (await meta.get_attribute("content") or "").strip().lower()
            if content in self.consent_values:
                return True

        html = page.locator("html").first
        if await html.count():
            attr = (
                await html.get_attribute("data-surveybot-automation") or ""
            ).strip().lower()
            if attr in self.consent_values:
                return True

        return False
