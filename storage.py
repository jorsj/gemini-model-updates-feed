"""Storage abstraction — local filesystem or GCS.

When the GCS_BUCKET env var is set, all read/write operations go to
Google Cloud Storage.  Otherwise they fall back to the local 'data/' directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_BUCKET_NAME: str | None = os.environ.get("GCS_BUCKET")

# Local fallback directory (same as before)
_LOCAL_DATA_DIR = Path(__file__).resolve().parent / "data"


def _gcs_client():
    """Lazy-import the GCS client so it's only required in Cloud Run."""
    from google.cloud import storage
    import google.auth

    # Explicitly request the cloud-platform scope to avoid legacy scope issues
    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return storage.Client(credentials=credentials, project=project)


def _gcs_blob(filename: str):
    client = _gcs_client()
    bucket = client.bucket(_BUCKET_NAME)
    return bucket.blob(f"data/{filename}")


# ── Public API ────────────────────────────────────────────────────────────────


def read_text(filename: str) -> str | None:
    """Read a text file.  Returns None if the file does not exist."""
    if _BUCKET_NAME:
        blob = _gcs_blob(filename)
        if not blob.exists():
            return None
        return blob.download_as_text(encoding="utf-8")
    else:
        path = _LOCAL_DATA_DIR / filename
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")


def write_text(filename: str, content: str) -> str:
    """Write a text file.  Returns the canonical path/URI written to."""
    if _BUCKET_NAME:
        blob = _gcs_blob(filename)
        blob.upload_from_string(content, content_type="text/plain; charset=utf-8")
        return f"gs://{_BUCKET_NAME}/data/{filename}"
    else:
        _LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOCAL_DATA_DIR / filename
        path.write_text(content, encoding="utf-8")
        return str(path.resolve())


def read_json(filename: str) -> dict | None:
    """Read a JSON file and return the parsed dict.  Returns None if missing."""
    text = read_text(filename)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def write_json(filename: str, data: dict) -> str:
    """Serialize *data* as pretty JSON and write it.  Returns the path/URI."""
    content = json.dumps(data, indent=2, ensure_ascii=False)
    content_type = "application/json; charset=utf-8"
    if _BUCKET_NAME:
        blob = _gcs_blob(filename)
        blob.upload_from_string(content, content_type=content_type)
        return f"gs://{_BUCKET_NAME}/data/{filename}"
    else:
        _LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = _LOCAL_DATA_DIR / filename
        path.write_text(content, encoding="utf-8")
        return str(path.resolve())
