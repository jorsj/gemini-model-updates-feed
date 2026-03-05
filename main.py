#!/usr/bin/env python3
"""CLI entry point for the Gemini deprecation tracker."""

from __future__ import annotations

import json
import sys

from tools import run_pipeline


def main() -> None:
    result = run_pipeline()

    changes = result["changes"]
    feed_path = result["feed_path"]
    item_count = result["item_count"]
    is_first_run = result["is_first_run"]

    if is_first_run:
        print("ℹ️  First run — no previous snapshot to compare against.")
        print()

    if not changes:
        print("✅ No changes detected.")
        return

    # Human-readable summary
    _PREFIXES = {
        "new_model": "🆕 New model",
        "deleted_model": "🗑️  Deleted model",
        "deprecation_date_changed": "📅 Date changed",
        "deprecating_soon": "⚠️  Deprecating soon",
    }

    print(f"Found {len(changes)} change(s):\n")
    for c in changes:
        prefix = _PREFIXES.get(c["change_type"], c["change_type"])
        print(f"  {prefix}: {c['model']}")
        print(f"    {c['summary']}")
        print()

    print(f"📄 Feed written to: {feed_path}")
    print(f"   Total items in feed: {item_count}")


if __name__ == "__main__":
    main()
