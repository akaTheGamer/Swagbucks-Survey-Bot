# Mock Survey QA Automation Bot

This project is a local QA harness for testing survey automation logic against owned mock pages. It does not automate Swagbucks or any live paid survey platform.

## Install

```bash
python -m pip install -e ".[test]"
python -m playwright install chromium
```

## Run against the bundled mock server

```bash
python -m surveybot --serve-mock --headed --config config/profile.json --log logs/survey_results.csv
```

Unknown non-profile questions are answered randomly. Stable profile-backed questions such as age, income, country, language, and car ownership are answered consistently from `config/profile.json`.

You can also run the mock site separately:

```bash
python -m surveybot.mock_server --host 127.0.0.1 --port 8000
python -m surveybot --headed --config config/profile.json --log logs/survey_results.csv
```

## Test

```bash
python -m pytest
```

The Playwright integration test skips automatically if Playwright or the Chromium browser binary is not installed.
