# ABOUTME: Live integration tests for the packaged Global AI Regulation Tracker client.
# ABOUTME: Verifies real API responses parse correctly when AI_REG_TRACKER_API_KEY is available.

from datetime import date

import pytest

from ai_reg_tracker.client import (
    NewsCategory,
    RegulationEntry,
    RegulationQuery,
    RegulationResponse,
    RegulationTrackerClient,
)


def _assert_entry_shape(resp: RegulationResponse) -> None:
    """Assert the common response structure for populated live responses."""
    assert isinstance(resp, RegulationResponse)
    assert resp.raw is not None
    assert isinstance(resp.entries, list)
    assert resp.entries

    first = resp.entries[0]
    assert isinstance(first, RegulationEntry)
    assert first.label is not None
    assert first.href is not None or first.link is not None
    assert first.desc is not None
    assert first.categories is not None


def _run_live_query(
    client: RegulationTrackerClient,
    market: str,
    category: NewsCategory | None = None,
    target_date: date | None = None,
    lang: str = 'eng',
) -> RegulationResponse:
    """Execute a live query and assert the response parses correctly."""
    query = RegulationQuery(
        market=market,
        category=category,
        date=target_date,
        lang=lang,
    )
    resp = client.query(query)
    _assert_entry_shape(resp)
    return resp


@pytest.mark.live
def test_live_global_date(live_client: RegulationTrackerClient) -> None:
    """Verify the global daily digest response parses correctly."""
    _run_live_query(
        client=live_client,
        market='global',
        target_date=date(2025, 3, 18),
    )


@pytest.mark.live
def test_live_us_category(live_client: RegulationTrackerClient) -> None:
    """Verify category-only single-market queries parse correctly."""
    _run_live_query(
        client=live_client,
        market='US',
        category='latest_news',
    )


@pytest.mark.live
def test_live_cn_date(live_client: RegulationTrackerClient) -> None:
    """Verify date-only single-market queries parse correctly."""
    _run_live_query(
        client=live_client,
        market='CN',
        target_date=date(2024, 12, 18),
    )


@pytest.mark.live
def test_live_us_full(live_client: RegulationTrackerClient) -> None:
    """Verify category and date queries parse correctly."""
    _run_live_query(
        client=live_client,
        market='US',
        category='latest_news',
        target_date=date(2024, 10, 3),
    )


@pytest.mark.live
def test_error_messages(live_client: RegulationTrackerClient) -> None:
    """Verify application-level API errors surface in response.message."""
    cases: list[tuple[str, RegulationQuery, str]] = [
        (
            'missing arguments',
            RegulationQuery(market='US'),
            'missing arguments',
        ),
        (
            'global date format',
            RegulationQuery(market='global'),
            'date provided',
        ),
        (
            'invalid country code',
            RegulationQuery(market='ZZZNOTAMARKET', category='latest_news'),
            'country code is invalid',
        ),
        (
            'future date',
            RegulationQuery(market='US', date=date(2026, 12, 31), category='latest_news'),
            'No news updates',
        ),
    ]

    for _, query, expected_fragment in cases:
        resp = live_client.query(query)
        assert resp.entries == []
        assert resp.message is not None
        assert expected_fragment.lower() in resp.message.lower()


@pytest.mark.live
def test_live_chinese_output(live_client: RegulationTrackerClient) -> None:
    """Verify Chinese-language output is reachable and parseable."""
    _run_live_query(
        client=live_client,
        market='CN',
        category='latest_news',
        lang='chn',
    )
