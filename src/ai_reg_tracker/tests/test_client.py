# ABOUTME: Unit tests for the packaged API client and query models.
# ABOUTME: Verifies local serialization and validation behavior without network access.

from datetime import date

import pytest

from ai_reg_tracker.client import RegulationQuery


def test_request_serialisation() -> None:
    """Verify RegulationQuery serialises to the expected HTTP body."""
    query = RegulationQuery(
        market='US',
        category='latest_news',
        date=date(2024, 10, 3),
        lang='eng',
    )
    body = query.to_http_body('TESTKEY')

    assert body['countryCode'] == 'US'
    assert body['targetNews'] == 'latest_news'
    assert body['targetDate'] == '2024-10-03'
    assert body['langCode'] == 'eng'
    assert body['apiKey'] == 'TESTKEY'

    empty_query = RegulationQuery(market='global')
    empty_body = empty_query.to_http_body('K')
    assert empty_body['targetNews'] == ''
    assert empty_body['targetDate'] == ''


def test_market_validation_rejects_blank_market() -> None:
    """Verify blank market codes raise a validation error."""
    with pytest.raises(ValueError, match='market must not be empty'):
        RegulationQuery(market='  ')


def test_market_validation_strips_whitespace() -> None:
    """Verify market values are normalized by trimming whitespace."""
    query = RegulationQuery(market='  US  ')
    assert query.market == 'US'
