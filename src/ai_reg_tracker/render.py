# ABOUTME: Renders Global AI Regulation Tracker API results as markdown files.
# ABOUTME: Exposes a Python function and a CLI; output records query params and timestamp.

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date as Date, datetime, timezone
from pathlib import Path

from ai_reg_tracker.client import (
    RegulationTrackerClient,
    RegulationQuery,
    RegulationResponse,
    RegulationEntry,
)

logger = logging.getLogger(__name__)

_LANG_LABELS: dict[str, str] = {
    'eng': 'English',
    'chn': 'Chinese (Simplified)',
}

_ALL_CATEGORIES: list[str] = [
    'latest_news',
    'sector_news',
    'bilateral_multilateral_news',
    'official_materials',
    'acts_bills_reform',
    'orders_admin_regs',
    'guidelines_standards_frameworks',
]


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------

def _auto_filename(q: RegulationQuery) -> str:
    """Build a descriptive filename from query params."""
    parts = [q.market]
    if q.category:
        parts.append(q.category)
    if q.date:
        parts.append(str(q.date))
    if q.lang != 'eng':
        parts.append(q.lang)
    return '_'.join(parts) + '.md'


def _title(q: RegulationQuery) -> str:
    """Build a human-readable document title from query params."""
    parts = [q.market]
    if q.category:
        parts.append(q.category.replace('_', ' '))
    if q.date:
        parts.append(str(q.date))
    return ' / '.join(parts)


def _render_entry(i: int, entry: RegulationEntry) -> list[str]:
    """Render a single entry as markdown lines."""
    label = (entry.label or '').strip().rstrip(':')
    desc = (entry.desc or '').strip()
    cats = (entry.categories or '').strip()
    url = entry.href or entry.link or ''

    lines: list[str] = []
    lines.append('---')
    lines.append('')
    lines.append(f'## {i}. {label}')
    lines.append('')
    if cats:
        lines.append(f'**Categories:** {cats}  ')
    if url:
        lines.append(f'**Source:** <{url}>  ')
    if cats or url:
        lines.append('')
    if desc:
        lines.append(desc)
        lines.append('')
    return lines


def _render_markdown(q: RegulationQuery, resp: RegulationResponse, max_entries: int) -> str:
    """Render a full API response as a markdown document string.

    Args:
        q: The query that produced this response.
        resp: The parsed API response.
        max_entries: Maximum number of entries to include. 0 means all.
            Positive values take the most recent N (last in the list).

    Returns:
        A complete markdown document as a string.
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    total = len(resp.entries)
    shown = resp.entries if max_entries <= 0 else resp.entries[-max_entries:]

    lines: list[str] = []

    # Title and query metadata
    lines.append(f'# AI Regulation — {_title(q)}')
    lines.append('')
    lines.append('| Parameter | Value |')
    lines.append('|---|---|')
    lines.append(f'| Market | `{q.market}` |')
    if q.category:
        lines.append(f'| Category | `{q.category}` |')
    else:
        lines.append(r'| Category | *(default: latest\_news + sector\_news + bilateral)* |')
    if q.date:
        lines.append(f'| Date | `{q.date}` |')
    else:
        lines.append('| Date | *(all dates)* |')
    lines.append(f'| Language | {_LANG_LABELS.get(q.lang, q.lang)} |')
    lines.append(f'| Fetched | {now} |')
    lines.append(f'| Total entries | {total} |')
    lines.append('')

    # No-data / error case
    if resp.message:
        lines.append(f'> ⚠️ {resp.message}')
        lines.append('')
        return '\n'.join(lines)

    if not resp.entries:
        lines.append('*No entries returned.*')
        lines.append('')
        return '\n'.join(lines)

    # Entry count note when capped
    if max_entries > 0 and total > max_entries:
        lines.append(f'*Showing {len(shown)} most recent of {total} total entries.*')
        lines.append('')

    for i, entry in enumerate(shown, 1):
        lines.extend(_render_entry(i, entry))

    return '\n'.join(lines)


def _resolve_output(output_arg: str | None, q: RegulationQuery) -> Path:
    """Resolve the output path from the CLI argument.

    - None → CWD / auto-filename
    - Existing directory or path ending with / → that directory / auto-filename
    - Anything else → treated as a literal file path
    """
    if output_arg is None:
        return Path.cwd() / _auto_filename(q)
    p = Path(output_arg)
    if p.is_dir() or output_arg.endswith(('/', os.sep)):
        return p / _auto_filename(q)
    return p


# ---------------------------------------------------------------------------
# Public Python API
# ---------------------------------------------------------------------------

def save_response(
    query: RegulationQuery,
    resp: RegulationResponse,
    output: Path,
    *,
    max_entries: int = 0,
) -> Path:
    """Save an already-fetched API response as a markdown file.

    Args:
        query: The query that produced this response.
        resp: The parsed API response.
        output: Destination path for the markdown file. If this is a directory,
            an auto-generated filename is appended.
        max_entries: Maximum entries to write. 0 means write all. Positive values
            keep the most recent N entries (last in the returned list).

    Returns:
        The resolved, absolute path of the saved file.
    """
    output = output.resolve()
    if output.is_dir():
        output = output / _auto_filename(query)

    content = _render_markdown(query, resp, max_entries)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    logger.info('RAY render: %d entries → %s', len(resp.entries), output)
    return output


def fetch_and_save(
    query: RegulationQuery,
    output: Path,
    *,
    client: RegulationTrackerClient,
    max_entries: int = 0,
) -> Path:
    """Fetch API results for a query and save them as a markdown file.

    Args:
        query: The regulation query to execute.
        output: Destination path for the markdown file. If this is a directory,
            an auto-generated filename is appended.
        client: Configured API client.
        max_entries: Maximum entries to write. 0 means write all. Positive values
            keep the most recent N entries (last in the returned list).

    Returns:
        The resolved, absolute path of the saved file.

    Raises:
        ValueError: On API transport failure or non-JSON response.
    """
    resp = client.query(query)
    return save_response(query, resp, output, max_entries=max_entries)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='ai-reg-render',
        description=(
            'Fetch Global AI Regulation Tracker results and save as a markdown file.\n\n'
            'API key is read from the AI_REG_TRACKER_API_KEY environment variable, '
            'or passed via --api-key.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--market', required=True,
        help='Jurisdiction/group code (e.g. US, CN, global, G7, OECD).',
    )
    parser.add_argument(
        '--category', default=None, choices=_ALL_CATEGORIES,
        metavar='CATEGORY',
        help=(
            'News category. One of: ' + ', '.join(_ALL_CATEGORIES) + '. '
            'Omit to use the API default (latest_news + sector_news + bilateral).'
        ),
    )
    parser.add_argument(
        '--date', default=None, metavar='YYYY-MM-DD',
        help='Target date. Omit to return all available dates.',
    )
    parser.add_argument(
        '--lang', default='eng', choices=['eng', 'chn'],
        help='Output language (default: eng).',
    )
    parser.add_argument(
        '--output', default=None, metavar='PATH',
        help=(
            'Output path. A directory means the auto-generated filename is used inside it. '
            'Defaults to ./<market>_<category>_<date>.md in the current directory.'
        ),
    )
    parser.add_argument(
        '--max-entries', type=int, default=0, metavar='N',
        help='Cap on entries written (0 = all, default). Positive N keeps the most recent N.',
    )
    parser.add_argument(
        '--api-key', default=None,
        help='API key (overrides AI_REG_TRACKER_API_KEY env var).',
    )
    return parser


def _cli_main() -> None:
    """Entry point for the ``ai-reg-render`` console script."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        parsed_date = Date.fromisoformat(args.date) if args.date else None
    except ValueError:
        parser.error(f'--date must be in YYYY-MM-DD format, got: {args.date!r}')

    try:
        query = RegulationQuery(
            market=args.market,
            category=args.category,
            date=parsed_date,
            lang=args.lang,
        )
    except ValueError as e:
        parser.error(str(e))

    output_path = _resolve_output(args.output, query)

    try:
        client = RegulationTrackerClient(args.api_key)
        saved = fetch_and_save(query, output_path, client=client, max_entries=args.max_entries)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'Saved: {saved}')


if __name__ == '__main__':
    _cli_main()
