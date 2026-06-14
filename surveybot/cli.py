from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import ConfigLoader
from .logger import CsvSurveyLogger
from .mock_server import run_mock_server
from .navigator import SurveyNavigator
from .question_handler import QuestionHandler
from .training import TrainingRecorder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local mock survey QA automation bot."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--headless", action="store_true", help="Run browser headlessly.")
    mode.add_argument("--headed", action="store_true", help="Run browser visibly.")
    parser.add_argument("--config", default="config/profile.json", help="Path to JSON config.")
    parser.add_argument("--log", default="logs/survey_results.csv", help="CSV log path.")
    parser.add_argument("--base-url", help="Override target.base_url from config.")
    parser.add_argument(
        "--target-mode",
        choices=["mock", "authorized"],
        help="Override target.mode from config.",
    )
    parser.add_argument(
        "--allowed-domain",
        action="append",
        default=None,
        help="Add/override an authorized public domain. Repeat for multiple domains.",
    )
    parser.add_argument(
        "--authorization-note",
        help="Permission note required for authorized public-domain runs.",
    )
    parser.add_argument(
        "--training-log",
        help="Append question/decision training records to this JSONL file.",
    )
    parser.add_argument(
        "--serve-mock",
        action="store_true",
        help="Start the bundled mock server for this run.",
    )
    parser.add_argument("--mock-host", default="127.0.0.1")
    parser.add_argument("--mock-port", default=8000, type=int)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    base_url = args.base_url
    if args.serve_mock and not base_url:
        base_url = f"http://{args.mock_host}:{args.mock_port}"

    loader = ConfigLoader(Path(args.config))
    config = loader.load(
        base_url_override=base_url,
        target_mode_override=args.target_mode,
        allowed_domains_override=args.allowed_domain,
        authorization_note_override=args.authorization_note,
    )
    logger = CsvSurveyLogger(args.log)
    handler = QuestionHandler(config.profile)
    training_recorder = TrainingRecorder(args.training_log) if args.training_log else None
    navigator = SurveyNavigator(
        config, logger, handler, training_recorder=training_recorder
    )
    headless = not args.headed

    if args.serve_mock:
        with run_mock_server(args.mock_host, args.mock_port):
            results = asyncio.run(navigator.run(headless=headless))
    else:
        results = asyncio.run(navigator.run(headless=headless))

    completed = sum(1 for result in results if result.status == "completed")
    disqualified = sum(1 for result in results if result.status == "disqualified")
    errors = sum(1 for result in results if result.status == "error")
    print(
        f"Logged {len(results)} survey attempts: "
        f"{completed} completed, {disqualified} disqualified, {errors} errors."
    )
    if args.training_log:
        print(f"Training records appended to {args.training_log}.")
