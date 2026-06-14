from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Protocol, Sequence

from .config import Profile


@dataclass(frozen=True)
class AnswerOption:
    label: str
    value: str
    index: int = 0


@dataclass(frozen=True)
class AnswerDecision:
    selected: AnswerOption
    strategy: str


class RandomSource(Protocol):
    def choice(self, seq: Sequence[AnswerOption]) -> AnswerOption:
        ...

    def randrange(self, stop: int) -> int:
        ...


class QuestionHandler:
    """Chooses answers on the local mock survey page."""

    def __init__(self, profile: Profile, rng: RandomSource | None = None):
        self.profile = profile
        self.rng = rng or random.Random()

    async def answer_current_question(
        self, page, recorder=None
    ) -> AnswerOption | list[AnswerOption]:
        form = page.locator("[data-testid='survey-question']")
        question_text = (await form.locator("[data-question-text]").inner_text()).strip()

        if await form.locator("[data-testid='survey-grid']").count():
            options = await self._read_grid_options(form)
            chosen_grid_options = await self._answer_grid(form)
            if recorder:
                recorder.record(
                    source_url=page.url,
                    question_kind="grid",
                    question_text=question_text,
                    profile_key=await form.get_attribute("data-profile-key"),
                    strategy="grid_randomized",
                    options=options,
                    selected=chosen_grid_options,
                )
            await form.locator("[data-testid='continue']").click()
            return chosen_grid_options

        profile_key = await form.get_attribute("data-profile-key")
        options = await self._read_options(form)

        decision = self.choose_answer_with_reason(
            question_text, options, profile_key=profile_key
        )
        chosen = decision.selected
        if recorder:
            recorder.record(
                source_url=page.url,
                question_kind="single",
                question_text=question_text,
                profile_key=profile_key,
                strategy=decision.strategy,
                options=options,
                selected=chosen,
            )
        await form.locator("input[name='answer']").nth(chosen.index).check()
        await form.locator("[data-testid='continue']").click()
        return chosen

    async def _read_options(self, form) -> list[AnswerOption]:
        labels = form.locator("[data-testid='answer-option']")
        options: list[AnswerOption] = []

        for index in range(await labels.count()):
            label = labels.nth(index)
            input_element = label.locator("input[name='answer']")
            value = await input_element.get_attribute("value")
            text = (await label.inner_text()).strip()
            options.append(AnswerOption(label=text, value=value or text, index=index))

        if not options:
            raise ValueError("No answer options found on the current question.")

        return options

    async def _read_grid_options(self, form) -> list[AnswerOption]:
        first_row = form.locator("[data-testid='grid-row']").first
        labels = first_row.locator("[data-testid='grid-option']")
        options: list[AnswerOption] = []

        for index in range(await labels.count()):
            label = labels.nth(index)
            input_element = label.locator("input[type='radio']")
            value = await input_element.get_attribute("value")
            text = (await label.inner_text()).strip()
            options.append(AnswerOption(label=text, value=value or text, index=index))

        if not options:
            raise ValueError("No grid answer options found on the current question.")

        return options

    def choose_answer(
        self,
        question_text: str,
        options: Sequence[AnswerOption],
        *,
        profile_key: str | None = None,
    ) -> AnswerOption:
        return self.choose_answer_with_reason(
            question_text, options, profile_key=profile_key
        ).selected

    def choose_answer_with_reason(
        self,
        question_text: str,
        options: Sequence[AnswerOption],
        *,
        profile_key: str | None = None,
    ) -> AnswerDecision:
        if not options:
            raise ValueError("Cannot choose an answer without options.")

        explicit = self.resolve_attention_answer(question_text, options)
        if explicit:
            return AnswerDecision(explicit, "explicit_instruction")

        key = (profile_key or "").strip().lower()
        if key == "age":
            return AnswerDecision(self._answer_age(options), "profile_age")
        if key == "gender":
            return AnswerDecision(
                self._answer_text(options, self.profile.gender), "profile_gender"
            )
        if key == "income":
            return AnswerDecision(self._answer_income(options), "profile_income")
        if key == "interests":
            return AnswerDecision(self._answer_interest(options), "profile_interests")
        if key == "country":
            return AnswerDecision(
                self._answer_text(options, self.profile.country), "profile_country"
            )
        if key == "language":
            return AnswerDecision(
                self._answer_text(options, self.profile.language), "profile_language"
            )
        if key == "owns_car":
            return AnswerDecision(
                self._answer_yes_no(options, self.profile.owns_car),
                "profile_owns_car",
            )
        if key == "car_insurance":
            if self.profile.owns_car:
                return AnswerDecision(
                    self.rng.choice(options), "random_car_insurance"
                )
            return AnswerDecision(self._answer_no_car(options), "consistency_no_car")

        return AnswerDecision(self.rng.choice(options), "random")

    async def _answer_grid(self, form) -> list[AnswerOption]:
        rows = form.locator("[data-testid='grid-row']")
        row_count = await rows.count()
        if row_count == 0:
            raise ValueError("Grid question did not contain any rows.")

        choices: list[tuple[int, int]] = []
        for row_index in range(row_count):
            row = rows.nth(row_index)
            option_count = await row.locator("input[type='radio']").count()
            if option_count == 0:
                raise ValueError("Grid row did not contain any answer options.")
            choices.append((row_index, self.rng.randrange(option_count)))

        column_choices = [choice for _, choice in choices]
        if row_count > 1 and len(set(column_choices)) == 1:
            row = rows.nth(row_count - 1)
            option_count = await row.locator("input[type='radio']").count()
            if option_count > 1:
                choices[-1] = (row_count - 1, (choices[-1][1] + 1) % option_count)

        selected: list[AnswerOption] = []
        for row_index, option_index in choices:
            row = rows.nth(row_index)
            option = row.locator("input[type='radio']").nth(option_index)
            label = row.locator("[data-testid='grid-option']").nth(option_index)
            value = await option.get_attribute("value")
            text = (await label.inner_text()).strip()
            await option.check()
            selected.append(AnswerOption(label=text, value=value or text, index=option_index))

        return selected

    def resolve_attention_answer(
        self, question_text: str, options: Sequence[AnswerOption]
    ) -> AnswerOption | None:
        normalized_question = _normalize_words(question_text)

        # Match longer labels first so "Blue" wins before a short value like "B".
        sorted_options = sorted(
            options,
            key=lambda option: max(len(option.label), len(option.value)),
            reverse=True,
        )
        for option in sorted_options:
            candidates = {_normalize_words(option.label), _normalize_words(option.value)}
            for candidate in candidates:
                if not candidate:
                    continue
                phrases = [
                    f"please choose {candidate}",
                    f"please select {candidate}",
                    f"please pick {candidate}",
                    f"choose {candidate}",
                    f"select {candidate}",
                    f"pick {candidate}",
                    f"please choose option {candidate}",
                    f"please select option {candidate}",
                    f"choose option {candidate}",
                    f"select option {candidate}",
                    f"correct answer is {candidate}",
                    f"the correct answer is {candidate}",
                    f"answer is {candidate}",
                    f"the answer is {candidate}",
                ]
                if any(_contains_phrase(normalized_question, phrase) for phrase in phrases):
                    return option

        return None

    def _answer_age(self, options: Sequence[AnswerOption]) -> AnswerOption:
        for option in options:
            if _age_in_label(self.profile.age, option.label):
                return option
        return options[0]

    def _answer_text(
        self, options: Sequence[AnswerOption], desired_value: str
    ) -> AnswerOption:
        desired = _normalize_words(desired_value)
        for option in options:
            label = _normalize_words(option.label)
            value = _normalize_words(option.value)
            if desired in {label, value} or _contains_phrase(label, desired):
                return option
        return options[0]

    def _answer_income(self, options: Sequence[AnswerOption]) -> AnswerOption:
        desired = _normalize_money(self.profile.income)
        for option in options:
            if desired in {
                _normalize_money(option.label),
                _normalize_money(option.value),
            }:
                return option
        return self._answer_text(options, self.profile.income)

    def _answer_interest(self, options: Sequence[AnswerOption]) -> AnswerOption:
        desired_interests = [_normalize_words(item) for item in self.profile.interests]
        for interest in desired_interests:
            for option in options:
                label = _normalize_words(option.label)
                value = _normalize_words(option.value)
                if _contains_phrase(label, interest) or _contains_phrase(value, interest):
                    return option
        return options[0]

    def _answer_yes_no(
        self, options: Sequence[AnswerOption], desired_value: bool
    ) -> AnswerOption:
        desired_terms = {"yes"} if desired_value else {"no", "none", "do not"}
        for option in options:
            label = _normalize_words(option.label)
            value = _normalize_words(option.value)
            if any(_contains_phrase(label, term) for term in desired_terms):
                return option
            if any(_contains_phrase(value, term) for term in desired_terms):
                return option
        return options[0]

    def _answer_no_car(self, options: Sequence[AnswerOption]) -> AnswerOption:
        preferred_terms = ["do not own a car", "no car", "none", "not applicable"]
        for term in preferred_terms:
            for option in options:
                label = _normalize_words(option.label)
                value = _normalize_words(option.value)
                if _contains_phrase(label, term) or _contains_phrase(value, term):
                    return option
        return options[0]


def _normalize_words(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_phrase(haystack: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _normalize_money(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", value.lower())


def _age_in_label(age: int, label: str) -> bool:
    normalized = label.lower()

    range_match = re.search(r"(\d{1,3})\s*[-\u2013]\s*(\d{1,3})", normalized)
    if range_match:
        lower, upper = int(range_match.group(1)), int(range_match.group(2))
        return lower <= age <= upper

    plus_match = re.search(r"(\d{1,3})\s*\+", normalized)
    if plus_match:
        return age >= int(plus_match.group(1))

    under_match = re.search(r"(?:under|below)\s*(\d{1,3})", normalized)
    if under_match:
        return age < int(under_match.group(1))

    exact_match = re.search(r"\b(\d{1,3})\b", normalized)
    if exact_match:
        return age == int(exact_match.group(1))

    return False
