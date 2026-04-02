# ABOUTME: HTTP client for the Global AI Regulation Tracker API by Raymond Sun.
# ABOUTME: Typed Pydantic request/response models and a single-method wrapper around the POST endpoint.

from __future__ import annotations

import logging
import os
from datetime import date as Date
from typing import Any, Dict, List, Literal, Optional, Tuple, TypeAlias

import requests
from pydantic import BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)

_ENDPOINT = 'https://globalairegtrackerapi-j66zxhj6dq-uc.a.run.app'


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

NewsCategory: TypeAlias = Literal[
    'latest_news',
    'sector_news',
    'bilateral_multilateral_news',
    'official_materials',
    'acts_bills_reform',
    'orders_admin_regs',
    'guidelines_standards_frameworks',
]

LangCode: TypeAlias = Literal['eng', 'chn']


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class RegulationQuery(BaseModel):
    """Query parameters for the regulation tracker.

    Valid query patterns:

    - ``market=<country>`` + ``category`` → full history for that market/category
    - ``market=<country>`` + ``category`` + ``date`` → single-day snapshot
    - ``market=<country>`` + ``date`` (no category) → all developments on that date
    - ``market='global'`` + ``date`` → dict[market_code → entries] across all markets
    - ``market=<group>`` (G7, G20, OECD, ASEAN, COE) + ``category`` → group history
      (group markets return "no data" for date queries, they are category-only)

    Invalid patterns — the API returns an error message, not an HTTP error:
    - Any market with no category AND no date: ``"Error - missing arguments..."``
    - ``market='global'`` without a date (any category): ``"Error - date not in valid format"``
    - ``official_materials`` for some markets is tier/market-gated
    - ``'EU'`` is not a valid code; use specific country codes or ``'Europe'`` for COE queries

    Args:
        market: Jurisdiction/group code (e.g. 'US', 'CN', 'global', 'G7', 'OECD').
        category: News category to filter by. When None the API defaults to
            searching latest_news, sector_news, and bilateral_multilateral_news.
            Use an explicit value for official_materials, acts_bills_reform,
            orders_admin_regs, and guidelines_standards_frameworks.
        date: Specific date to query. When None, returns all available dates.
        lang: Output language code. Defaults to English.
    """

    market: str
    category: Optional[NewsCategory] = None
    date: Optional[Date] = None
    lang: LangCode = 'eng'

    @field_validator('market')
    @classmethod
    def market_must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('market must not be empty')
        return v.strip()

    def to_http_body(self, api_key: str) -> Dict[str, str]:
        """Serialize to the raw HTTP request body format expected by the API."""
        return {
            'countryCode': self.market,
            'targetNews': self.category or '',
            'targetDate': self.date.isoformat() if self.date else '',
            'langCode': self.lang,
            'apiKey': api_key,
        }


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class RegulationEntry(BaseModel):
    """A single regulation entry returned by the API.

    All four core fields are always present when the API returns real data.
    Unknown fields are preserved via ``model_extra``.

    Attributes:
        label: Headline in ``[DD Month YYYY] Title:`` format.
        desc: Full description of the regulatory development.
        href: Source URL. Always present.
        link: Source URL. Present only in global+date dict responses; mirrors href.
        categories: Comma-separated category tags (e.g. ``"Generative AI, Cybersecurity"``).
    """

    model_config = ConfigDict(extra='allow')

    label: Optional[str] = None
    desc: Optional[str] = None
    href: Optional[str] = None
    link: Optional[str] = None
    categories: Optional[str] = None

    @property
    def categories_list(self) -> list[str]:
        """Return the categories as a list of strings."""
        if not self.categories:
            return []
        return [c.strip() for c in self.categories.split(',')]

class RegulationResponse(BaseModel):
    """Parsed response from a single API call.

    The raw API response takes two shapes depending on the query:

    - **list** — for single/group market queries (the common case).
    - **dict keyed by market code** — only for ``market='global'`` + date queries,
      where entries from multiple markets are bucketed under their country key.

    Both shapes are flattened into ``entries``. When the API returns no data or
    an error (e.g. invalid market code), ``entries`` is empty and ``message``
    carries the API's informational string.

    Attributes:
        entries: Flattened list of regulation entries.
        message: Info or error string from the API when no entries are returned.
        raw: Original JSON payload, preserved verbatim.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    entries: List[RegulationEntry]
    message: Optional[str] = None
    raw: Any


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

def _extract_entries(payload: Any) -> Tuple[List[RegulationEntry], Optional[str]]:
    """Best-effort extraction of entries from the raw API payload.

    Returns a tuple of (entries, message) where message is non-None when the
    API responded with an informational or error string instead of data.

    Handles the two documented response shapes:
    - **list of dicts** — standard per-market/category results.
    - **dict of lists** — global+date results keyed by market code.

    The API also returns ``["some string"]`` (a list with one string element)
    when there are no results or when the market code is invalid.
    """
    if isinstance(payload, list):
        entries = [RegulationEntry.model_validate(item) for item in payload if isinstance(item, dict)]
        if not entries:
            strings = [item for item in payload if isinstance(item, str)]
            message = strings[0] if strings else None
            return [], message
        return entries, None

    if isinstance(payload, dict):
        entries = []
        for value in payload.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        entries.append(RegulationEntry.model_validate(item))
        return entries, None

    logger.warning('Unexpected response type %s', type(payload).__name__)
    return [], None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class RegulationTrackerClient:
    """Client for the Global AI Regulation Tracker API.

    Args:
        api_key: Subscription API key. Falls back to the ``AI_REG_TRACKER_API_KEY``
            environment variable when not provided.
        timeout: Request timeout in seconds.

    Raises:
        ValueError: If no API key is provided and ``AI_REG_TRACKER_API_KEY`` is not set.
    """

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        resolved = api_key or os.environ.get('AI_REG_TRACKER_API_KEY')
        if not resolved:
            raise ValueError(
                'API key must be provided or set via the AI_REG_TRACKER_API_KEY environment variable'
            )
        self._api_key: str = resolved
        self._timeout = timeout

    def query(self, q: RegulationQuery) -> RegulationResponse:
        """Send a query and return parsed results.

        Args:
            q: Query parameters.

        Returns:
            RegulationResponse with parsed entries and the raw payload.

        Raises:
            ValueError: On HTTP transport failure or non-JSON response.
        """
        body = q.to_http_body(self._api_key)
        logger.info('RAY API query: market=%r category=%r date=%s', q.market, q.category, q.date)

        try:
            resp = requests.post(_ENDPOINT, json=body, timeout=self._timeout)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise ValueError(f'RAY API HTTP error {resp.status_code}: {resp.text[:400]}') from e
        except requests.exceptions.RequestException as e:
            raise ValueError(f'RAY API transport error: {e}') from e

        try:
            raw = resp.json()
        except ValueError as e:
            raise ValueError(f'RAY API returned non-JSON: {resp.text[:400]}') from e

        entries, message = _extract_entries(raw)
        logger.info(
            'RAY API response: %d entries parsed from %s%s',
            len(entries),
            type(raw).__name__,
            f' — message: {message!r}' if message else '',
        )

        return RegulationResponse(entries=entries, message=message, raw=raw)
