"""Deterministic diff between two parsed deprecation snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from parser import ModelRow

DEPRECATING_SOON_DAYS = 90


@dataclass(frozen=True)
class Change:
    """One detected change between snapshots."""

    change_type: str   # "new_model" | "deleted_model" | "deprecation_date_changed" | "deprecating_soon"
    model: str
    category: str
    summary: str
    old_value: str = ""
    new_value: str = ""
    deprecation_date: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "change_type": self.change_type,
            "model": self.model,
            "category": self.category,
            "summary": self.summary,
        }
        if self.old_value:
            d["old_value"] = self.old_value
        if self.new_value:
            d["new_value"] = self.new_value
        if self.deprecation_date:
            d["deprecation_date"] = self.deprecation_date
        return d


def _format_date(d: date | None) -> str:
    """Format a date for display, or return empty string."""
    if d is None:
        return ""
    return d.strftime("%B %-d, %Y")


def _format_date_iso(d: date | None) -> str:
    """Format a date as YYYY-MM-DD, or return empty string."""
    if d is None:
        return ""
    return d.isoformat()


def _is_deprecating_soon(shutdown: date | None, today: date) -> bool:
    """Return True if the shutdown date is set and within DEPRECATING_SOON_DAYS of today."""
    if shutdown is None:
        return False
    # Only flag if shutdown is in the future (or today) and within the window
    return today <= shutdown <= today + timedelta(days=DEPRECATING_SOON_DAYS)


def diff_snapshots(
    previous: list[ModelRow],
    current: list[ModelRow],
    today: date | None = None,
) -> list[Change]:
    """Compare two parsed snapshots and return a list of Changes.

    Categories of changes detected:
      1. new_model       — model in current but not in previous
      2. deleted_model   — model in previous but not in current
      3. deprecation_date_changed — shutdown_date differs between snapshots
      4. deprecating_soon — shutdown_date is within 90 days from today

    On first run (previous is empty), all current models are reported as
    new_model, plus any that are deprecating_soon.
    """
    if today is None:
        today = date.today()

    prev_map: dict[str, ModelRow] = {row.key(): row for row in previous}
    curr_map: dict[str, ModelRow] = {row.key(): row for row in current}

    changes: list[Change] = []

    # ── New models ────────────────────────────────────────────────────────
    for key, row in curr_map.items():
        if key not in prev_map:
            changes.append(
                Change(
                    change_type="new_model",
                    model=row.model,
                    category=row.category,
                    summary=f"New model added: {row.model}.",
                    new_value=_format_date(row.shutdown_date) or "No shutdown date announced",
                    deprecation_date=_format_date_iso(row.shutdown_date),
                )
            )

    # ── Deleted models ────────────────────────────────────────────────────
    for key, row in prev_map.items():
        if key not in curr_map:
            changes.append(
                Change(
                    change_type="deleted_model",
                    model=row.model,
                    category=row.category,
                    summary=f"Model removed from deprecation page: {row.model}.",
                    old_value=_format_date(row.shutdown_date) or "No shutdown date",
                    deprecation_date=_format_date_iso(row.shutdown_date),
                )
            )

    # ── Deprecation date changed ──────────────────────────────────────────
    for key in curr_map:
        if key in prev_map:
            curr_row = curr_map[key]
            prev_row = prev_map[key]
            if curr_row.shutdown_date != prev_row.shutdown_date:
                old_val = _format_date(prev_row.shutdown_date) or "No shutdown date"
                new_val = _format_date(curr_row.shutdown_date) or "No shutdown date"
                changes.append(
                    Change(
                        change_type="deprecation_date_changed",
                        model=curr_row.model,
                        category=curr_row.category,
                        summary=(
                            f"Shutdown date for {curr_row.model} changed "
                            f"from {old_val} to {new_val}."
                        ),
                        old_value=old_val,
                        new_value=new_val,
                        deprecation_date=_format_date_iso(curr_row.shutdown_date),
                    )
                )

    # ── Deprecating soon ──────────────────────────────────────────────────
    # Check ALL current models, regardless of whether they are new or existing
    for key, row in curr_map.items():
        if _is_deprecating_soon(row.shutdown_date, today):
            changes.append(
                Change(
                    change_type="deprecating_soon",
                    model=row.model,
                    category=row.category,
                    summary=(
                        f"Model {row.model} is shutting down on "
                        f"{_format_date(row.shutdown_date)}."
                    ),
                    new_value=_format_date(row.shutdown_date),
                    deprecation_date=_format_date_iso(row.shutdown_date),
                )
            )

    # Sort for deterministic output: by change_type then model name
    type_order = {
        "new_model": 0,
        "deleted_model": 1,
        "deprecation_date_changed": 2,
        "deprecating_soon": 3,
    }
    changes.sort(key=lambda c: (type_order.get(c.change_type, 99), c.model))

    return changes
