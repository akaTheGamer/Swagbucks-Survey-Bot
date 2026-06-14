from __future__ import annotations

from surveybot.mock_server import SURVEYS


def all_question_text() -> str:
    texts: list[str] = []
    for survey in SURVEYS.values():
        for question in survey["questions"]:
            texts.append(question["text"])
    return "\n".join(texts).lower()


def test_quality_check_fixture_contains_requested_examples():
    text = all_question_text()

    assert "strongly disagree" in text
    assert "visited every country" in text
    assert "do not own a car" in text
    assert "blorvex ultra cereal" in text
    assert "flarn the greebles" in text
    assert "same column for every row" in text
    assert "15 minutes" in text
    assert "which color did we ask you to remember" in text
    assert "age consistency" in text
    assert "which country do you live in" in text
    assert "which language should this mock survey use" in text


def test_quality_check_fixture_contains_grid_question():
    quality_questions = SURVEYS["quality-check-lab"]["questions"]
    grid_questions = [
        question for question in quality_questions if question.get("type") == "grid"
    ]

    assert len(grid_questions) == 1
    assert len(grid_questions[0]["rows"]) >= 3
    assert len(grid_questions[0]["columns"]) >= 3
