from __future__ import annotations

import argparse
import collections
import json
from collections.abc import Sequence as SequenceCollection
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .question_handler import AnswerOption


@dataclass(frozen=True)
class TrainingRecord:
    timestamp: str
    source_url: str
    question_kind: str
    question_text: str
    profile_key: str
    strategy: str
    options: list[dict[str, Any]]
    selected: list[dict[str, Any]]
    label: str = "unlabeled"


class TrainingRecorder:
    """Append-only JSONL recorder for question/decision training examples."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def record(
        self,
        *,
        source_url: str,
        question_kind: str,
        question_text: str,
        profile_key: str | None,
        strategy: str,
        options: Sequence[AnswerOption],
        selected: AnswerOption | Sequence[AnswerOption],
        label: str = "unlabeled",
    ) -> None:
        selected_options = (
            list(selected)
            if isinstance(selected, SequenceCollection)
            and not isinstance(selected, AnswerOption)
            else [selected]
        )
        record = TrainingRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_url=source_url,
            question_kind=question_kind,
            question_text=question_text,
            profile_key=profile_key or "",
            strategy=strategy,
            options=[_option_to_dict(option) for option in options],
            selected=[_option_to_dict(option) for option in selected_options],
            label=label,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def _option_to_dict(option: AnswerOption) -> dict[str, Any]:
    return {
        "label": option.label,
        "value": option.value,
        "index": option.index,
    }


def load_records(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def summarize_records(path: str | Path) -> dict[str, Any]:
    records = load_records(path)
    strategy_counts = collections.Counter(record["strategy"] for record in records)
    profile_key_counts = collections.Counter(record["profile_key"] for record in records)
    return {
        "total_records": len(records),
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "profile_key_counts": dict(sorted(profile_key_counts.items())),
        "unlabeled_records": sum(
            1 for record in records if record.get("label") == "unlabeled"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect surveybot training logs.")
    parser.add_argument("--input", required=True, help="JSONL training log path.")
    args = parser.parse_args()

    print(json.dumps(summarize_records(args.input), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
