from __future__ import annotations

import argparse
import contextlib
import html
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator
from urllib.parse import parse_qs, urlencode, urlparse


SURVEYS = {
    "tech-fit": {
        "title": "Technology Fit Survey",
        "earnings": 0.50,
        "questions": [
            {
                "text": "What is your age range?",
                "profile_key": "age",
                "options": [
                    ("18-24", "18-24"),
                    ("25-34", "25-34"),
                    ("35-44", "35-44"),
                    ("45+", "45+"),
                ],
            },
            {
                "text": "To show you're paying attention, please choose Blue.",
                "profile_key": "",
                "options": [("red", "Red"), ("blue", "Blue"), ("green", "Green")],
            },
            {
                "text": "Which topic are you most interested in?",
                "profile_key": "interests",
                "options": [
                    ("sports", "Sports"),
                    ("technology", "Technology"),
                    ("cooking", "Cooking"),
                ],
            },
        ],
    },
    "income-screen": {
        "title": "Income Screen Survey",
        "earnings": 0.75,
        "questions": [
            {
                "text": "Which income range best matches your household?",
                "profile_key": "income",
                "options": [
                    ("0-25000", "$0 - $25,000"),
                    ("25000-50000", "$25,000 - $50,000"),
                    ("50000-75000", "$50,000 - $75,000"),
                    ("100000+", "$100,000+"),
                ],
                "disqualify_unless": "100000+",
                "disqualify_note": "Mock client only wants high-income respondents.",
            }
        ],
    },
    "attention-lab": {
        "title": "Attention Check Lab",
        "earnings": 1.00,
        "questions": [
            {
                "text": "Please select 'Strongly disagree' for this question.",
                "profile_key": "",
                "options": [
                    ("strongly_disagree", "Strongly disagree"),
                    ("disagree", "Disagree"),
                    ("agree", "Agree"),
                    ("strongly_agree", "Strongly agree"),
                ],
            },
            {
                "text": "Please choose option C to continue.",
                "profile_key": "",
                "options": [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
            },
            {
                "text": (
                    "Which of the following is NOT a fruit? "
                    "The correct answer is Car."
                ),
                "profile_key": "",
                "options": [
                    ("apple", "Apple"),
                    ("banana", "Banana"),
                    ("car", "Car"),
                    ("orange", "Orange"),
                ],
            },
        ],
    },
    "quality-check-lab": {
        "title": "Survey Quality Check Lab",
        "earnings": 1.25,
        "questions": [
            {
                "text": "Do you own a car?",
                "profile_key": "owns_car",
                "options": [("yes", "Yes"), ("no", "No")],
            },
            {
                "text": (
                    "Contradiction check: earlier you said you do not own a car. "
                    "Which car insurance provider do you use?"
                ),
                "profile_key": "car_insurance",
                "options": [
                    ("none", "I do not own a car"),
                    ("acme_auto", "Acme Auto"),
                    ("contoso_cover", "Contoso Cover"),
                    ("northwind_insurance", "Northwind Insurance"),
                ],
            },
            {
                "text": "Impossible claim check: I have visited every country in the world.",
                "profile_key": "",
                "options": [("yes", "Yes"), ("no", "No")],
            },
            {
                "text": (
                    "Fake brand check: have you bought Blorvex Ultra Cereal "
                    "in the past 7 days?"
                ),
                "profile_key": "",
                "options": [("yes", "Yes"), ("no", "No"), ("not_sure", "Not sure")],
            },
            {
                "text": "Nonsense-word check: how often do you flarn the greebles?",
                "profile_key": "",
                "options": [
                    ("never", "Never"),
                    ("rarely", "Rarely"),
                    ("sometimes", "Sometimes"),
                    ("often", "Often"),
                ],
            },
            {
                "type": "grid",
                "text": (
                    "Too-perfect behavior check: rate each row. The mock bot "
                    "should avoid selecting the same column for every row."
                ),
                "profile_key": "",
                "rows": [
                    ("checkout", "The checkout process was clear."),
                    ("support", "Customer support answered quickly."),
                    ("pricing", "The pricing page was easy to compare."),
                ],
                "columns": [
                    ("strongly_disagree", "Strongly disagree"),
                    ("disagree", "Disagree"),
                    ("agree", "Agree"),
                    ("strongly_agree", "Strongly agree"),
                ],
            },
            {
                "text": "For a later memory check, please choose Purple.",
                "profile_key": "",
                "options": [
                    ("red", "Red"),
                    ("purple", "Purple"),
                    ("yellow", "Yellow"),
                ],
            },
            {
                "text": "Memory check: earlier, which color did we ask you to remember? The answer is Purple.",
                "profile_key": "",
                "options": [
                    ("red", "Red"),
                    ("purple", "Purple"),
                    ("yellow", "Yellow"),
                ],
            },
            {
                "text": "Age consistency check: choose your age range again.",
                "profile_key": "age",
                "options": [
                    ("18-24", "18-24"),
                    ("25-34", "25-34"),
                    ("35-44", "35-44"),
                    ("45+", "45+"),
                ],
            },
            {
                "text": "Location check: which country do you live in?",
                "profile_key": "country",
                "options": [
                    ("Germany", "Germany"),
                    ("United States", "United States"),
                    ("France", "France"),
                ],
            },
            {
                "text": "Language check: which language should this mock survey use?",
                "profile_key": "language",
                "options": [
                    ("English", "English"),
                    ("German", "German"),
                    ("Spanish", "Spanish"),
                ],
            },
            {
                "text": (
                    "Speed check fixture: this survey is labeled as 15 minutes "
                    "but was completed in 90 seconds. What should the mock QA "
                    "review?"
                ),
                "profile_key": "",
                "options": [
                    ("timing", "Completion timing"),
                    ("colors", "Color preference"),
                    ("brand", "Brand familiarity"),
                ],
            },
        ],
    },
}


class MockSurveyHandler(BaseHTTPRequestHandler):
    server_version = "MockSurveyHTTP/0.1"

    def do_GET(self) -> None:
        route = urlparse(self.path)
        if route.path in {"/", "/login"}:
            self._send_html(self._login_page())
            return

        if route.path == "/surveys":
            if not self._has_session():
                self._redirect("/login")
                return
            self._send_html(self._surveys_page())
            return

        if route.path.startswith("/survey/"):
            if not self._has_session():
                self._redirect("/login")
                return
            survey_id = route.path.removeprefix("/survey/")
            query = parse_qs(route.query)
            question_index = int(query.get("q", ["0"])[0])
            self._send_html(self._question_page(survey_id, question_index))
            return

        if route.path == "/result":
            if not self._has_session():
                self._redirect("/login")
                return
            query = parse_qs(route.query)
            self._send_html(
                self._result_page(
                    survey_id=query.get("survey_id", ["unknown"])[0],
                    status=query.get("status", ["error"])[0],
                    earnings=query.get("earnings", ["0.00"])[0],
                    notes=query.get("notes", [""])[0],
                )
            )
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        route = urlparse(self.path)
        if route.path == "/login":
            self._redirect("/surveys", headers={"Set-Cookie": "mock_session=1; Path=/"})
            return

        if route.path.startswith("/survey/") and route.path.endswith("/answer"):
            if not self._has_session():
                self._redirect("/login")
                return

            survey_id = route.path.removeprefix("/survey/").removesuffix("/answer")
            form = self._read_form()
            question_index = int(form.get("q", ["0"])[0])
            answer = form.get("answer", [""])[0]
            self._handle_answer(survey_id, question_index, answer)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _handle_answer(self, survey_id: str, question_index: int, answer: str) -> None:
        survey = SURVEYS.get(survey_id)
        if not survey:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        questions = survey["questions"]
        question = questions[question_index]
        required_answer = question.get("disqualify_unless")
        if required_answer and answer != required_answer:
            self._redirect(
                "/result?"
                + urlencode(
                    {
                        "survey_id": survey_id,
                        "status": "disqualified",
                        "earnings": "0.00",
                        "notes": question.get("disqualify_note", "Disqualified."),
                    }
                )
            )
            return

        next_index = question_index + 1
        if next_index >= len(questions):
            self._redirect(
                "/result?"
                + urlencode(
                    {
                        "survey_id": survey_id,
                        "status": "completed",
                        "earnings": f"{survey['earnings']:.2f}",
                        "notes": "Mock survey completed.",
                    }
                )
            )
            return

        self._redirect(f"/survey/{survey_id}?q={next_index}")

    def _login_page(self) -> str:
        return _page(
            "Mock Login",
            """
            <main>
              <h1>Mock Survey Login</h1>
              <form method="post" action="/login">
                <label>Username <input name="username" autocomplete="username"></label>
                <label>Password <input name="password" type="password" autocomplete="current-password"></label>
                <button data-testid="login-submit" type="submit">Log in</button>
              </form>
            </main>
            """,
        )

    def _surveys_page(self) -> str:
        cards = []
        for survey_id, survey in SURVEYS.items():
            cards.append(
                f"""
                <article data-testid="survey-card"
                         data-survey-id="{html.escape(survey_id)}"
                         data-earnings="{survey['earnings']:.2f}">
                  <h2>{html.escape(survey['title'])}</h2>
                  <p>Mock earnings: {survey['earnings']:.2f}</p>
                  <a data-testid="survey-link" href="/survey/{html.escape(survey_id)}?q=0">Start</a>
                </article>
                """
            )
        return _page("Mock Surveys", "<main><h1>Available Mock Surveys</h1>" + "".join(cards) + "</main>")

    def _question_page(self, survey_id: str, question_index: int) -> str:
        survey = SURVEYS.get(survey_id)
        if not survey or question_index >= len(survey["questions"]):
            return _page("Missing Survey", "<main><h1>Survey not found</h1></main>")

        question = survey["questions"][question_index]
        question_type = question.get("type", "single")
        controls = (
            self._grid_controls(question)
            if question_type == "grid"
            else self._single_choice_controls(question)
        )

        body = f"""
        <main>
          <h1>{html.escape(survey['title'])}</h1>
          <form data-testid="survey-question"
                data-question-kind="{html.escape(question_type)}"
                data-profile-key="{html.escape(question.get('profile_key', ''))}"
                method="post"
                action="/survey/{html.escape(survey_id)}/answer">
            <input type="hidden" name="q" value="{question_index}">
            <fieldset>
              <legend data-question-text>{html.escape(question['text'])}</legend>
              {controls}
            </fieldset>
            <button data-testid="continue" type="submit">Continue</button>
          </form>
        </main>
        """
        return _page(survey["title"], body)

    def _single_choice_controls(self, question: dict) -> str:
        options = []
        for value, label in question["options"]:
            options.append(
                f"""
                <label data-testid="answer-option">
                  <input type="radio" name="answer" value="{html.escape(value)}" required>
                  {html.escape(label)}
                </label>
                """
            )
        return "".join(options)

    def _grid_controls(self, question: dict) -> str:
        rows = []
        for row_id, row_label in question["rows"]:
            options = []
            for value, label in question["columns"]:
                options.append(
                    f"""
                    <label data-testid="grid-option">
                      <input type="radio"
                             name="grid_{html.escape(row_id)}"
                             value="{html.escape(value)}"
                             required>
                      {html.escape(label)}
                    </label>
                    """
                )
            rows.append(
                f"""
                <div data-testid="grid-row" data-row-id="{html.escape(row_id)}">
                  <p>{html.escape(row_label)}</p>
                  {''.join(options)}
                </div>
                """
            )

        return f'<div data-testid="survey-grid">{"".join(rows)}</div>'

    def _result_page(
        self, *, survey_id: str, status: str, earnings: str, notes: str
    ) -> str:
        body = f"""
        <main data-testid="result" data-survey-id="{html.escape(survey_id)}">
          <h1>Survey Result</h1>
          <p>Status: <span data-testid="result-status">{html.escape(status)}</span></p>
          <p>Mock earnings: <span data-testid="result-earnings">{html.escape(earnings)}</span></p>
          <p data-testid="result-notes">{html.escape(notes)}</p>
          <a href="/surveys">Back to surveys</a>
        </main>
        """
        return _page("Survey Result", body)

    def _has_session(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        return "mock_session=1" in cookie

    def _read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return parse_qs(body)

    def _redirect(self, location: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="en" data-surveybot-automation="allowed">
      <head>
        <meta charset="utf-8">
        <meta name="surveybot-automation" content="allowed">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{html.escape(title)}</title>
        <style>
          body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 720px; }}
          main, form, article {{ display: grid; gap: 1rem; }}
          article {{ border: 1px solid #ccc; padding: 1rem; }}
          label {{ display: block; margin: .5rem 0; }}
          button, a {{ justify-self: start; }}
        </style>
      </head>
      <body>{body}</body>
    </html>
    """


@contextlib.contextmanager
def run_mock_server(host: str = "127.0.0.1", port: int = 8000) -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer((host, port), MockSurveyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the bundled mock survey server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    with run_mock_server(args.host, args.port):
        print(f"Mock survey server running at http://{args.host}:{args.port}")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            print("\nStopping mock survey server.")


if __name__ == "__main__":
    main()
