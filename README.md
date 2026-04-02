# ai-reg-tracker

Python client for [Raymond Sun's Global AI Regulation Tracker API](https://globalairegtrackerapi-j66zxhj6dq-uc.a.run.app).
Covers subscription-gated access to AI regulatory developments across ~100+ jurisdictions.

## Installation

```bash
pip install ai-reg-tracker
```

Or install from source:

```bash
git clone https://github.com/aegis-blue-ai/ai-reg-tracker.git
cd ai-reg-tracker
pip install -e .
```

## API key

Purchase a plan from the **API Access** tab on the Global AI Regulation Tracker website.
After payment you are redirected to a page displaying your unique API key.

Set it as the `AI_REG_TRACKER_API_KEY` environment variable, or pass `api_key=` directly to the client.

## Quick start

```python
from ai_reg_tracker import RegulationTrackerClient, RegulationQuery
from datetime import date

client = RegulationTrackerClient()  # uses AI_REG_TRACKER_API_KEY env var

# Full category history for a single market
resp = client.query(RegulationQuery(market='US', category='latest_news'))
for entry in resp.entries:
    print(entry.label)
    print(entry.href)
    print(entry.desc[:120])
    print()

# All markets active on a specific date
resp = client.query(RegulationQuery(market='global', date=date(2025, 3, 18)))

# Single-day snapshot for one market
resp = client.query(RegulationQuery(market='CN', date=date(2024, 12, 18)))

# Always check for empty results
if resp.message:
    print(f'No data: {resp.message}')
```

## Response model

Every call returns a `RegulationResponse`:

| Field | Type | Description |
|---|---|---|
| `entries` | `list[RegulationEntry]` | Flattened list of developments |
| `message` | `str \| None` | API info/error string when entries is empty |
| `raw` | `Any` | Original JSON payload, verbatim |

Each `RegulationEntry` has four fields that are always populated when real data is returned:

| Field | Description |
|---|---|
| `label` | Headline; format varies by category |
| `desc` | Full description of the regulatory development |
| `href` | Source URL (always present) |
| `categories` | Comma-separated topic tags, e.g. `"Generative AI, Cybersecurity"` |
| `link` | Source URL — mirrors `href`, present only in `global`+date responses |

`RegulationEntry` uses `extra='allow'` so any new fields the API adds are preserved in `model_extra`.

## Query parameter reference

```python
RegulationQuery(
    market   = 'US',              # required — see Market codes below
    category = 'latest_news',     # optional — see Categories below
    date     = date(2024, 10, 3), # optional — YYYY-MM-DD
    lang     = 'eng',             # optional — 'eng' (default) or 'chn'
)
```

### Valid query patterns

| Pattern | `market` | `category` | `date` | Response shape |
|---|---|---|---|---|
| Category history | country/group | ✓ | — | `list[entry]` |
| Single-day snapshot | country/group | ✓ | ✓ | `list[entry]` |
| All developments on a date | country | — | ✓ | `list[entry]` |
| Global daily digest | `'global'` | — | ✓ | `dict[market → list[entry]]`* |
| Group category history | G7 / G20 / OECD / ASEAN / COE | ✓ | — | `list[entry]` |

\* The `global`+date response is a dict keyed by market code. `resp.entries` flattens this automatically.

### Categories

| Value | Tracker section |
|---|---|
| `latest_news` | Latest Macro Developments |
| `sector_news` | Sector Developments |
| `bilateral_multilateral_news` | Bilateral & Multilateral Developments |
| `official_materials` | Official Materials |
| `acts_bills_reform` | Acts, Bills & Reforms |
| `orders_admin_regs` | Executive & Regulatory Instruments |
| `guidelines_standards_frameworks` | Guidelines, Frameworks & Standards |

When `category` is omitted the API searches `latest_news`, `sector_news`, and
`bilateral_multilateral_news` by default.

### Market codes

A selection of verified codes:

| Code | Jurisdiction |
|---|---|
| `global` | All markets (requires `date`) |
| `US` | United States |
| `CN` | China |
| `AU` | Australia |
| `CA` | Canada |
| `JP` | Japan |
| `IN` | India |
| `GB` | United Kingdom |
| `KR` | South Korea |
| `G7` | G7 |
| `G20` | G20 |
| `OECD` | OECD |
| `ASEAN` | ASEAN |
| `COE` | Council of Europe |

`EU` is **not** a valid standalone code — use country-level codes or `COE`.

## Error handling

The client raises `ValueError` only for transport-level failures (network errors,
non-200 HTTP responses, malformed JSON). Application-level errors (bad market code,
missing arguments, no data) come back as `resp.message` with `resp.entries == []`.

```python
try:
    resp = client.query(q)
except ValueError as e:
    # Network / HTTP / JSON parse failure
    print(f'API call failed: {e}')

if resp.message:
    # Bad query parameters or no data for this combination
    print(f'API returned no data: {resp.message}')
```

## Rendering results to markdown

The package includes a renderer that saves API results as self-contained markdown files.

### CLI

```bash
# Full category history
ai-reg-render --market US --category latest_news

# Single-day global digest, saved to a specific directory
ai-reg-render --market global --date 2025-03-18 --output ./output/

# Explicit output path, capped at 10 most recent entries
ai-reg-render --market G7 --category acts_bills_reform \
  --max-entries 10 --output ./g7_bills.md
```

| Flag | Default | Description |
|---|---|---|
| `--market` | *(required)* | Jurisdiction/group code |
| `--category` | *(none)* | News category |
| `--date YYYY-MM-DD` | *(none)* | Target date |
| `--lang` | `eng` | `eng` or `chn` |
| `--output PATH` | `./<auto>.md` | File path or directory |
| `--max-entries N` | `0` (all) | Keep only the N most recent entries |
| `--api-key KEY` | `AI_REG_TRACKER_API_KEY` env var | API key |

### Python API

```python
from datetime import date
from pathlib import Path
from ai_reg_tracker import RegulationTrackerClient, RegulationQuery, fetch_and_save

client = RegulationTrackerClient()

saved = fetch_and_save(
    query=RegulationQuery(market='US', category='latest_news'),
    output=Path('output/'),
    client=client,
    max_entries=0,
)
print(f'Saved: {saved}')
```

## Running tests

The package uses `pytest` with a split test layout:

- `test_client.py` for unit tests with no network access
- `test_live_api.py` for live integration tests against the real API

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests only
pytest -m "not live"

# Run live API tests
AI_REG_TRACKER_API_KEY=your_key pytest -m live

# Run the full suite
AI_REG_TRACKER_API_KEY=your_key pytest
```

## Licence

MIT — see [LICENSE](LICENSE).

The tracker API itself is subscription-gated. Confirm your licence tier before
any productised or customer-facing integration.
