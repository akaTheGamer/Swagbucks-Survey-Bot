from __future__ import annotations

from surveybot.config import Profile
from surveybot.question_handler import AnswerOption, QuestionHandler


class LastOptionRandom:
    def choice(self, seq):
        return seq[-1]

    def randrange(self, stop: int) -> int:
        return 0


def handler(rng=None) -> QuestionHandler:
    return QuestionHandler(
        Profile(
            age=34,
            gender="female",
            income="50000-75000",
            interests=["technology", "travel"],
        ),
        rng=rng,
    )


def options(*labels: str) -> list[AnswerOption]:
    return [AnswerOption(label=label, value=label, index=index) for index, label in enumerate(labels)]


def test_resolves_explicit_attention_check_answer():
    chosen = handler().choose_answer(
        "To show you're paying attention, please choose Blue.",
        options("Red", "Blue", "Green"),
    )

    assert chosen.label == "Blue"


def test_resolves_direct_instruction_check_answer():
    chosen = handler(rng=LastOptionRandom()).choose_answer(
        "Please select 'Strongly disagree' for this question.",
        options("Strongly disagree", "Disagree", "Agree", "Strongly agree"),
    )

    assert chosen.label == "Strongly disagree"


def test_resolves_option_letter_attention_check_answer():
    chosen = handler().choose_answer(
        "Please choose option C to continue.",
        options("A", "B", "C", "D"),
    )

    assert chosen.label == "C"


def test_resolves_embedded_correct_answer_for_not_question():
    chosen = handler().choose_answer(
        "Which of the following is NOT a fruit? The correct answer is Car.",
        options("Apple", "Banana", "Car", "Orange"),
    )

    assert chosen.label == "Car"


def test_selects_age_from_profile_range():
    chosen = handler().choose_answer(
        "What is your age range?",
        options("18-24", "25-34", "35-44"),
        profile_key="age",
    )

    assert chosen.label == "25-34"


def test_selects_gender_from_profile():
    chosen = handler().choose_answer(
        "What is your gender?",
        options("Male", "Female", "Nonbinary"),
        profile_key="gender",
    )

    assert chosen.label == "Female"


def test_selects_income_from_profile():
    chosen = handler().choose_answer(
        "Which income range best matches your household?",
        [
            AnswerOption("$0 - $25,000", "0-25000", 0),
            AnswerOption("$50,000 - $75,000", "50000-75000", 1),
            AnswerOption("$100,000+", "100000+", 2),
        ],
        profile_key="income",
    )

    assert chosen.value == "50000-75000"


def test_selects_interest_from_profile():
    chosen = handler().choose_answer(
        "Which topic are you most interested in?",
        options("Sports", "Technology", "Cooking"),
        profile_key="interests",
    )

    assert chosen.label == "Technology"


def test_selects_country_and_language_from_profile():
    country = handler().choose_answer(
        "Location check: which country do you live in?",
        options("Germany", "United States", "France"),
        profile_key="country",
    )
    language = handler().choose_answer(
        "Language check: which language should this mock survey use?",
        options("English", "German", "Spanish"),
        profile_key="language",
    )

    assert country.label == "Germany"
    assert language.label == "German"


def test_selects_consistent_no_car_answer_from_profile():
    owns_car = handler().choose_answer(
        "Do you own a car?",
        options("Yes", "No"),
        profile_key="owns_car",
    )
    insurance = handler(rng=LastOptionRandom()).choose_answer(
        "Which car insurance provider do you use?",
        options("I do not own a car", "Acme Auto", "Contoso Cover"),
        profile_key="car_insurance",
    )

    assert owns_car.label == "No"
    assert insurance.label == "I do not own a car"


def test_unknown_non_profile_question_uses_random_answer():
    chosen = handler(rng=LastOptionRandom()).choose_answer(
        "Which snack do you prefer during the mock survey?",
        options("Chips", "Fruit", "Pretzels"),
    )

    assert chosen.label == "Pretzels"
