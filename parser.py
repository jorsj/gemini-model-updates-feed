"""Parse the Gemini deprecation markdown page into structured records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


# Matches "Month Day, Year"  e.g.  "March 9, 2026"
_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2}),\s+(\d{4})"
)

_MONTH_MAP: dict[str, int] = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def _parse_date(text: str) -> date | None:
    """Parse a human-readable date like 'March 9, 2026' into a date object."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    month = _MONTH_MAP[m.group(1)]
    day = int(m.group(2))
    year = int(m.group(3))
    return date(year, month, day)


@dataclass(frozen=True)
class ModelRow:
    """One row from a deprecation table."""

    model: str  # e.g. "gemini-2.5-flash"
    category: str  # the `## ` heading, e.g. "Gemini 3 models"
    release_date: date | None = None
    shutdown_date: date | None = None
    shutdown_date_raw: str = ""  # original text, for display
    replacement: str = ""

    def key(self) -> str:
        """Unique identity for diffing purposes."""
        return self.model


def parse_deprecation_page(markdown: str) -> list[ModelRow]:
    """Parse the markdown text and return a list of ModelRow records.

    The markdown is structured as:
      ## Section heading
      | **Model** | **Release date** | **Shutdown date** | **Recommended replacement** |
      |---|---|---|---|
      | `model-name` | ... | ... | ... |
      | Preview models ||||
      | `another-model` | ... | ... | ... |
    """
    rows: list[ModelRow] = []
    current_category = ""

    for line in markdown.splitlines():
        stripped = line.strip()

        # Detect section headings like "## Gemini 3 models"
        if stripped.startswith("## "):
            current_category = stripped.removeprefix("## ").strip()
            continue

        # Skip non-table lines
        if not stripped.startswith("|"):
            continue

        # Split cells (strip outer pipes)
        cells = [c.strip() for c in stripped.split("|")]
        # After split on "|", first and last elements are empty strings
        cells = cells[1:-1] if len(cells) >= 2 else cells

        if len(cells) < 4:
            continue

        model_cell = cells[0].strip()

        # Skip header rows
        if model_cell.startswith("**") or model_cell.startswith("---"):
            continue

        # Skip separator rows like "| Preview models ||||"
        # These lack backticks around the name
        if "`" not in model_cell:
            continue

        # Extract the model name from backticks
        backtick_match = re.search(r"`([^`]+)`", model_cell)
        if not backtick_match:
            continue

        model_name = backtick_match.group(1)

        release_text = cells[1].strip() if len(cells) > 1 else ""
        shutdown_text = cells[2].strip() if len(cells) > 2 else ""
        replacement_text = cells[3].strip() if len(cells) > 3 else ""

        # Clean replacement of backticks
        replacement_text = replacement_text.replace("`", "").strip()

        release_date = _parse_date(release_text)
        shutdown_date = _parse_date(shutdown_text)

        rows.append(
            ModelRow(
                model=model_name,
                category=current_category,
                release_date=release_date,
                shutdown_date=shutdown_date,
                shutdown_date_raw=shutdown_text,
                replacement=replacement_text,
            )
        )

    return rows
