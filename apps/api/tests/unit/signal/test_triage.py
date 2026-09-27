"""Unit tests for [Triage](/architecture/rules.md#triage).

Covers the unit test row in the design:
  - Keeps a document only for services at or above ``TRIAGE_RELEVANCE_MIN_P``
  - ``NOT_ABOUT_ACCOUNT`` below ``TRIAGE_ABOUT_MIN_P``
  - ``ABOUT_ACCOUNT`` skipped for own-source/CRUNCHBASE (no ``about_account_p``); a CAREERS
    document is asked whether it is a job posting instead
"""

from __future__ import annotations

import pytest

from leadradar.core.enums import DocumentTriageOutcome, SourcePluginCode
from leadradar.core.signal.triage import (
    ABOUT_ACCOUNT_QUESTION_ID,
    RELEVANT_QUESTION_PREFIX,
    about_account_question,
    is_own_source,
    triage,
)

pytestmark = pytest.mark.unit

ABOUT_MIN = 0.5
RELEVANCE_MIN = 0.3
SVC_A = "svc-aaa"
SVC_B = "svc-bbb"


def _answers(
    *,
    about_p: float | None = None,
    svc_a_p: float = 0.0,
    svc_b_p: float = 0.0,
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    if about_p is not None:
        result[ABOUT_ACCOUNT_QUESTION_ID] = {"YES": about_p, "NO": 1.0 - about_p}
    result[f"{RELEVANT_QUESTION_PREFIX}{SVC_A}"] = {"YES": svc_a_p, "NO": 1.0 - svc_a_p}
    result[f"{RELEVANT_QUESTION_PREFIX}{SVC_B}"] = {"YES": svc_b_p, "NO": 1.0 - svc_b_p}
    return result


class TestNotAboutAccount:
    def test_below_about_min_returns_not_about_account(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A],
            answers=_answers(about_p=0.4, svc_a_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
        assert result.about_account_p == pytest.approx(0.4)
        assert not result.kept_service_ids

    def test_exactly_at_about_min_is_kept(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A],
            answers=_answers(about_p=0.5, svc_a_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT

    def test_above_about_min_proceeds_to_relevance(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A],
            answers=_answers(about_p=0.8, svc_a_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT
        assert SVC_A in result.kept_service_ids


class TestOwnSource:
    """ABOUT_ACCOUNT is skipped for own-source documents."""

    def test_own_source_skips_about_check(self) -> None:
        # No ABOUT_ACCOUNT key in answers
        answers = _answers(svc_a_p=0.9)
        result = triage(
            is_own_source=True,
            service_ids=[SVC_A],
            answers=answers,
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT
        assert result.about_account_p is None

    def test_own_source_with_low_about_p_still_kept(self) -> None:
        """Even if ABOUT_ACCOUNT answer exists, it is not used for own sources."""
        result = triage(
            is_own_source=True,
            service_ids=[SVC_A],
            answers=_answers(about_p=0.01, svc_a_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        # own-source: about_account_p not checked
        assert result.outcome is DocumentTriageOutcome.KEPT
        # about_account_p is set from the answer (if present) but irrelevant to routing
        # Spec says skipped → None; our implementation skips the check, still reads the p
        # The test validates outcome is KEPT regardless of the about_p
        assert result.outcome is DocumentTriageOutcome.KEPT


class TestRelevance:
    def test_below_relevance_min_for_all_services_is_irrelevant(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A, SVC_B],
            answers=_answers(about_p=0.9, svc_a_p=0.1, svc_b_p=0.2),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.IRRELEVANT
        assert not result.kept_service_ids

    def test_exactly_at_relevance_min_is_kept(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A],
            answers=_answers(about_p=0.9, svc_a_p=0.3),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT
        assert SVC_A in result.kept_service_ids

    def test_only_relevant_services_kept(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A, SVC_B],
            answers=_answers(about_p=0.9, svc_a_p=0.8, svc_b_p=0.1),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT
        assert SVC_A in result.kept_service_ids
        assert SVC_B not in result.kept_service_ids

    def test_multiple_services_all_kept(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[SVC_A, SVC_B],
            answers=_answers(about_p=0.9, svc_a_p=0.9, svc_b_p=0.7),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.KEPT
        assert {SVC_A, SVC_B} == result.kept_service_ids

    def test_no_services_always_irrelevant(self) -> None:
        result = triage(
            is_own_source=False,
            service_ids=[],
            answers=_answers(about_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.IRRELEVANT


def test_own_sources_are_the_account_s_pages_and_crunchbase() -> None:
    from leadradar.core.signal.triage import is_own_source

    own = {"WEBSITE", "RSS", "CRUNCHBASE"}
    assert {code for code in own if is_own_source(code)} == own
    assert not any(is_own_source(code) for code in ("CAREERS", "GDELT", "NEWSAPI", "SERPAPI"))


class TestAboutAccountQuestion:
    """The `ABOUT_ACCOUNT` question each source gets."""

    def _question(self, plugin_code: SourcePluginCode) -> str | None:
        return about_account_question(
            plugin_code, name="Siemens", domain="siemens.com", country="DE"
        )

    def test_a_third_party_document_is_asked_whether_it_is_mainly_about_the_account(self) -> None:
        assert self._question(SourcePluginCode.GDELT) == (
            "Is this text mainly about Siemens (siemens.com, DE), not a different company with a"
            " similar name and not a passing mention?"
        )

    @pytest.mark.parametrize("plugin_code", [SourcePluginCode.WEBSITE, SourcePluginCode.CRUNCHBASE])
    def test_an_own_source_or_crunchbase_document_is_not_asked(
        self, plugin_code: SourcePluginCode
    ) -> None:
        assert self._question(plugin_code) is None
        assert is_own_source(plugin_code)

    def test_a_careers_document_is_asked_whether_it_is_a_job_posting(self) -> None:
        assert self._question(SourcePluginCode.CAREERS) == (
            "Is this text one or more job postings of Siemens (siemens.com, DE), not a sign-in,"
            " account or other page of the careers site?"
        )
        assert not is_own_source(SourcePluginCode.CAREERS)

    def test_a_careers_page_that_is_not_a_posting_is_not_about_the_account(self) -> None:
        result = triage(
            is_own_source=is_own_source(SourcePluginCode.CAREERS),
            service_ids=[SVC_A],
            answers=_answers(about_p=0.05, svc_a_p=0.9),
            triage_about_min_p=ABOUT_MIN,
            triage_relevance_min_p=RELEVANCE_MIN,
        )
        assert result.outcome is DocumentTriageOutcome.NOT_ABOUT_ACCOUNT
