from __future__ import annotations

from surveybot.question_handler import AnswerOption
from surveybot.training import TrainingRecorder, load_records, summarize_records


def test_training_recorder_writes_jsonl_records(tmp_path):
    path = tmp_path / "training.jsonl"
    recorder = TrainingRecorder(path)

    recorder.record(
        source_url="http://127.0.0.1:8000/survey/example?q=0",
        question_kind="single",
        question_text="Which mock option do you prefer?",
        profile_key="",
        strategy="random",
        options=[
            AnswerOption("Alpha", "alpha", 0),
            AnswerOption("Beta", "beta", 1),
        ],
        selected=AnswerOption("Beta", "beta", 1),
    )

    records = load_records(path)
    summary = summarize_records(path)

    assert records[0]["question_text"] == "Which mock option do you prefer?"
    assert records[0]["selected"][0]["value"] == "beta"
    assert summary["total_records"] == 1
    assert summary["strategy_counts"] == {"random": 1}
