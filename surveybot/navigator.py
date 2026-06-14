from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from urllib.parse import urljoin

from .adapters import DataAttributeSurveyAdapter
from .config import BotConfig
from .logger import CsvSurveyLogger, SurveyResult
from .question_handler import QuestionHandler
from .safety import assert_target_policy


@dataclass(frozen=True)
class SurveyLink:
    survey_id: str
    href: str
    mock_earnings: float


class SurveyNavigator:
    def __init__(
        self,
        config: BotConfig,
        logger: CsvSurveyLogger,
        question_handler: QuestionHandler,
        training_recorder=None,
        adapter: DataAttributeSurveyAdapter | None = None,
    ):
        assert_target_policy(
            config.target.base_url,
            mode=config.target.mode,
            allowed_domains=config.target.allowed_domains,
            authorization_note=config.target.authorization_note,
        )
        self.config = config
        self.logger = logger
        self.question_handler = question_handler
        self.training_recorder = training_recorder
        self.adapter = adapter or DataAttributeSurveyAdapter()

    async def run(self, *, headless: bool = True) -> list[SurveyResult]:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page()
            try:
                await self.login(page)
                surveys = await self.detect_surveys(page)
                results: list[SurveyResult] = []
                for survey in surveys:
                    result = await self.complete_survey(page, survey)
                    self.logger.log(result)
                    results.append(result)
                return results
            finally:
                await browser.close()

    async def login(self, page) -> None:
        await page.goto(self._url("/login"))
        await self.adapter.assert_target_allowed(page, self.config)
        await self._delay()
        await page.locator("input[name='username']").fill(self.config.login.username)
        await self._delay()
        await page.locator("input[name='password']").fill(self.config.login.password)
        await self._delay()
        await page.locator("[data-testid='login-submit']").click()
        await page.wait_for_url("**/surveys")

    async def detect_surveys(self, page) -> list[SurveyLink]:
        await page.goto(self._url("/surveys"))
        await self.adapter.assert_target_allowed(page, self.config)
        cards = page.locator("[data-testid='survey-card']")
        surveys: list[SurveyLink] = []

        for index in range(await cards.count()):
            card = cards.nth(index)
            survey_id = await card.get_attribute("data-survey-id")
            earnings = await card.get_attribute("data-earnings")
            href = await card.locator("[data-testid='survey-link']").get_attribute("href")
            if not survey_id or not href:
                continue
            survey_href = urljoin(self.config.target.base_url + "/", href)
            assert_target_policy(
                survey_href,
                mode=self.config.target.mode,
                allowed_domains=self.config.target.allowed_domains,
                authorization_note=self.config.target.authorization_note,
            )
            surveys.append(
                SurveyLink(
                    survey_id=survey_id,
                    href=survey_href,
                    mock_earnings=float(earnings or 0),
                )
            )

        return surveys

    async def complete_survey(self, page, survey: SurveyLink) -> SurveyResult:
        started_at = time.monotonic()
        try:
            await page.goto(survey.href)
            await self.adapter.assert_target_allowed(page, self.config)
            for _ in range(25):
                if await page.locator("[data-testid='result']").count():
                    return await self._read_result(page, survey, started_at)

                if await page.locator("[data-testid='survey-question']").count():
                    await self._delay()
                    await self.question_handler.answer_current_question(
                        page, recorder=self.training_recorder
                    )
                    await page.wait_for_load_state("domcontentloaded")
                    await self.adapter.assert_target_allowed(page, self.config)
                    await self._delay()
                    continue

                await page.wait_for_timeout(250)

            return SurveyResult(
                survey_id=survey.survey_id,
                status="error",
                mock_earnings=0.0,
                duration_seconds=time.monotonic() - started_at,
                notes="Survey did not reach a result page.",
            )
        except Exception as exc:
            return SurveyResult(
                survey_id=survey.survey_id,
                status="error",
                mock_earnings=0.0,
                duration_seconds=time.monotonic() - started_at,
                notes=f"{type(exc).__name__}: {exc}",
            )

    async def _read_result(
        self, page, survey: SurveyLink, started_at: float
    ) -> SurveyResult:
        status = (
            await page.locator("[data-testid='result-status']").inner_text()
        ).strip().lower()
        earnings_text = (
            await page.locator("[data-testid='result-earnings']").inner_text()
        ).strip()
        notes = (await page.locator("[data-testid='result-notes']").inner_text()).strip()

        return SurveyResult(
            survey_id=survey.survey_id,
            status=status,
            mock_earnings=float(earnings_text),
            duration_seconds=time.monotonic() - started_at,
            notes=notes,
        )

    async def _delay(self) -> None:
        minimum = self.config.automation.min_delay_seconds
        maximum = self.config.automation.max_delay_seconds
        await asyncio.sleep(random.uniform(minimum, maximum))

    def _url(self, path: str) -> str:
        return urljoin(self.config.target.base_url + "/", path.lstrip("/"))
