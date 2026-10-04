from datetime import UTC, datetime, timedelta

import pytest

from bank_agent.domain.retention import RATE_LIMIT_WINDOW_RETENTION, PurgeReport, RetentionPolicy

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def test_cutoffs_count_back_from_the_purge_instant() -> None:
    cutoffs = RetentionPolicy(conversation_days=7, session_days=3, credit_application_days=30).cutoffs(NOW)

    assert cutoffs.conversations == NOW - timedelta(days=7)
    assert cutoffs.sessions == NOW - timedelta(days=3)
    assert cutoffs.credit_applications == NOW - timedelta(days=30)
    assert cutoffs.rate_limit_windows == NOW - RATE_LIMIT_WINDOW_RETENTION


def test_a_policy_refuses_periods_under_a_day_and_naive_instants() -> None:
    with pytest.raises(ValueError, match="at least one day"):
        RetentionPolicy(conversation_days=0, session_days=7, credit_application_days=30)
    with pytest.raises(ValueError, match="timezone-aware"):
        RetentionPolicy(conversation_days=7, session_days=7, credit_application_days=30).cutoffs(
            datetime(2026, 10, 1, 12, 0)  # noqa: DTZ001
        )


def test_a_report_lists_counts_per_table_and_their_total() -> None:
    report = PurgeReport(messages=2, turns=1, conversations=1, sessions=3, rate_limit_windows=4)

    assert report.total == 11
    assert report.counts()["otp_challenges"] == 0
    assert not report.dry_run
