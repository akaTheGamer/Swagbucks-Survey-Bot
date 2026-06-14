from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class SurveyResult:
    survey_id: str
    status: str
    mock_earnings: float
    duration_seconds: float
    notes: str = ""
    timestamp: str = ""

    def as_row(self) -> dict[str, str]:
        timestamp = self.timestamp or datetime.now(timezone.utc).isoformat()
        return {
            "timestamp": timestamp,
            "survey_id": self.survey_id,
            "status": self.status,
            "mock_earnings": f"{self.mock_earnings:.2f}",
            "duration_seconds": f"{self.duration_seconds:.2f}",
            "notes": self.notes,
        }


class CsvSurveyLogger:
    FIELDNAMES = [
        "timestamp",
        "survey_id",
        "status",
        "mock_earnings",
        "duration_seconds",
        "notes",
    ]

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def log(self, result: SurveyResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        should_write_header = not self.path.exists() or self.path.stat().st_size == 0

        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.FIELDNAMES)
            if should_write_header:
                writer.writeheader()
            writer.writerow(result.as_row())
