"""Tools for the Gemini deprecation tracker — pure Python, no LLM."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx

import storage
from differ import Change, diff_snapshots
from parser import parse_deprecation_page

DEPRECATION_URL = "https://ai.google.dev/gemini-api/docs/deprecations.md.txt"

LATEST_FILE = "deprecations_latest.md.txt"
PREVIOUS_FILE = "deprecations_previous.md.txt"
FEED_FILE = "feed.json"


def fetch_deprecation_page() -> tuple[str, str, bool]:
    """Download the latest deprecation page, rotate snapshots.

    Returns:
        (current_markdown, previous_markdown, is_first_run)
    """
    # Load previous snapshot (if any)
    previous_markdown = storage.read_text(LATEST_FILE) or ""

    # Download current page
    response = httpx.get(DEPRECATION_URL, follow_redirects=True, timeout=30)
    response.raise_for_status()
    current_markdown = response.text

    # Rotate: current becomes latest, old latest becomes previous
    if previous_markdown:
        storage.write_text(PREVIOUS_FILE, previous_markdown)
    storage.write_text(LATEST_FILE, current_markdown)

    is_first_run = previous_markdown == ""
    return current_markdown, previous_markdown, is_first_run


def generate_feed(changes: list[Change]) -> tuple[str, int]:
    """Write the JSON Feed 1.1 file from a list of Change objects.

    Returns:
        (feed_path, item_count)
    """
    now = datetime.now(timezone.utc).isoformat()

    _PREFIXES = {
        "new_model": "🆕 New model",
        "deleted_model": "🗑️ Deleted model",
        "deprecation_date_changed": "📅 Deprecation date changed",
        "deprecating_soon": "⚠️ Deprecating soon",
    }

    items = []
    for change in changes:
        prefix = _PREFIXES.get(change.change_type, change.change_type)
        item_id = f"{change.change_type}-{change.model}-{now}"

        items.append(
            {
                "id": item_id,
                "title": f"{prefix}: {change.model}",
                "content_text": change.summary,
                "date_published": now,
                "_model_metadata": {
                    "model": change.model,
                    "category": change.category,
                    "deprecation_date": change.deprecation_date,
                },
                "tags": [change.change_type],
            }
        )

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Gemini API Model Deprecation Updates",
        "home_page_url": "https://ai.google.dev/gemini-api/docs/deprecations",
        "description": (
            "Automated feed tracking changes to Gemini API model deprecation "
            "schedules: new models, upcoming shutdowns, date changes, and "
            "removed models."
        ),
        "language": "en",
        "items": items,
    }

    if storage._BUCKET_NAME:
        feed["feed_url"] = (
            f"https://storage.googleapis.com/{storage._BUCKET_NAME}/data/feed.json"
        )

    # Merge with existing feed history
    old_feed = storage.read_json(FEED_FILE)
    if old_feed:
        existing_ids = {item["id"] for item in items}
        for old_item in old_feed.get("items", []):
            if old_item["id"] not in existing_ids:
                items.append(old_item)
        feed["items"] = items

    feed_path = storage.write_json(FEED_FILE, feed)
    return feed_path, len(items)


def run_pipeline(today: date | None = None) -> dict:
    """Run the full fetch → parse → diff → feed pipeline.

    Args:
        today: Override for "today" (useful for testing). Defaults to date.today().

    Returns:
        A dict with:
          - changes: list of change dicts
          - feed_path: path to the written feed.json
          - item_count: number of items in the feed
          - is_first_run: whether this was the first run
    """
    if today is None:
        today = date.today()

    # 1. Fetch
    current_md, previous_md, is_first_run = fetch_deprecation_page()

    # 2. Parse
    current_rows = parse_deprecation_page(current_md)
    previous_rows = parse_deprecation_page(previous_md) if previous_md else []

    # 3. Diff
    changes = diff_snapshots(previous_rows, current_rows, today=today)

    # 4. Generate feed
    if changes:
        feed_path, item_count = generate_feed(changes)
    else:
        feed_path = f"(no changes — {FEED_FILE} unchanged)"
        item_count = 0

    return {
        "changes": [c.to_dict() for c in changes],
        "feed_path": feed_path,
        "item_count": item_count,
        "is_first_run": is_first_run,
    }
