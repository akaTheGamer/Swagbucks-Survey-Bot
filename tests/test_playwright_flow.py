from __future__ import annotations

import asyncio
import csv
import json

import pytest

from surveybot.config import ConfigLoader
from surveybot.logger import CsvSurveyLogger
from surveybot.mock_server import run_mock_server
from surveybot.navigator import SurveyNavigator
from surveybot.question_handler import QuestionHandler
from surveybot.training import TrainingRecorder, summarize_records


def test_playwright_flow_against_mock_site(tmp_path):
    pytest.importorskip("playwright.async_api")

    try:
        asyncio.run(_run_flow(tmp_path))
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("Playwright Chromium browser is not installed.")
        raise


async def _run_flow(tmp_path):
    config_path = tmp_path / "profile.json"
    log_path = tmp_path / "survey_results.csv"
    training_path = tmp_path / "questions.jsonl"

    with run_mock_server("127.0.0.1", 0) as server:
        _, port = server.server_address
        config_path.write_text(
            json.dumps(
                {
                    "profile": {
                        "age": 34,
                        "gender": "female",
                        "income": "50000-75000",
                        "interests": ["technology", "travel"],
                        "country": "Germany",
                        "language": "German",
                        "owns_car": False,
                    },
                    "automation": {
                        "min_delay_seconds": 0,
                        "max_delay_seconds": 0,
                    },
                    "target": {
                        "base_url": f"http://127.0.0.1:{port}",
                    },
                }
            ),
            encoding="utf-8",
        )

        config = ConfigLoader(config_path).load()
        navigator = SurveyNavigator(
            config,
            CsvSurveyLogger(log_path),
            QuestionHandler(config.profile),
            training_recorder=TrainingRecorder(training_path),
        )
        results = await navigator.run(headless=True)

    statuses = {result.survey_id: result.status for result in results}
    assert statuses == {
        "tech-fit": "completed",
        "income-screen": "disqualified",
        "attention-lab": "completed",
        "quality-check-lab": "completed",
    }

    rows = list(csv.DictReader(log_path.open("r", encoding="utf-8")))
    assert len(rows) == 4
    assert {row["status"] for row in rows} == {"completed", "disqualified"}

    summary = summarize_records(training_path)
    assert summary["total_records"] >= 10
    assert summary["strategy_counts"]["explicit_instruction"] >= 1
    assert summary["strategy_counts"]["random"] >= 1
    assert summary["strategy_counts"]["grid_randomized"] == 1
