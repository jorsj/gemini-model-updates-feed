# Gemini Model Deprecation Tracker

A deterministic Python tool that monitors the [Gemini API deprecation page](https://ai.google.dev/gemini-api/docs/deprecations) for changes and publishes updates as a [JSON Feed 1.1](https://www.jsonfeed.org/version/1.1/).

## Live Feed

If you just want to consume the feed instead of deploying your own instance to GCP, a live version is automatically maintained and publicly available here:

`https://storage.googleapis.com/gemini-tracker-data-sandcastle-401718/data/feed.json`

## What it tracks

| Change type | Description |
|---|---|
| 🆕 `new_model` | A model was added to the deprecation page |
| 🗑️ `deleted_model` | A model was removed from the page |
| 📅 `deprecation_date_changed` | A model's shutdown date was modified |
| ⚠️ `deprecating_soon` | A model's shutdown date is within 90 days |

## Setup & Running Locally

```bash
# Install dependencies using uv
uv sync

# Run the pipeline locally
uv run python main.py
```

No API keys or LLM credentials required — the pipeline is pure Python. 
When run locally without the `GCS_BUCKET` environment variable set, the tool reads and writes files to the local `data/` directory.

## Cloud Deployment

The tracker can be deployed as a Google Cloud Run Job triggered daily by Cloud Scheduler. In the cloud, the tool uses Google Cloud Storage (GCS) to store the feed and snapshots, making them publicly accessible.

### One-Click Deploy to GCP

Ensure you are authenticated (`gcloud auth login`) and have a project configured (`gcloud config set project YOUR_PROJECT_ID`). Run the deployment script:

```bash
./deploy.sh
```

The script will automatically:
1. Enable necessary GCP APIs (Cloud Run, Scheduler, Build, IAM, Storage).
2. Create a globally unique GCS bucket `gemini-tracker-data-[PROJECT_ID]` with public read access.
3. Provision specific Service Accounts with least-privilege IAM roles.
4. Build the container from `Dockerfile` and deploy the Cloud Run Job.
5. Create a Cloud Scheduler trigger to run the job daily at 10:00 UTC.

Once deployed, your files are publicly accessible at:
* `https://storage.googleapis.com/gemini-tracker-data-[PROJECT_ID]/data/feed.json`
* `https://storage.googleapis.com/gemini-tracker-data-[PROJECT_ID]/data/deprecations_latest.md.txt`

## Output

After running, the tool creates/updates:

| File | Description |
|---|---|
| `feed.json` | JSON Feed 1.1 with all detected changes |
| `deprecations_latest.md.txt` | Most recent downloaded snapshot |
| `deprecations_previous.md.txt` | Previous snapshot (for diff on next run) |

### First run

On the first run there is no previous snapshot, so *all* models are reported as `new_model` and any with shutdown dates within 90 days are flagged as `deprecating_soon`.

### Subsequent runs

Only actual **differences** between the latest and previous snapshots produce new feed items. The feed history is preserved — new items are appended to the existing `feed.json`.

## Architecture

A 4-stage deterministic pipeline (no LLM calls):

```
fetch → parse → diff → feed
```

1. **Fetch** (`tools.fetch_deprecation_page`) — Downloads the deprecation page from `ai.google.dev`, rotates the previous/latest snapshots via the storage layer.
2. **Parse** (`parser.parse_deprecation_page`) — Parses the markdown tables into structured `ModelRow` dataclass records, extracting model names, dates, and categories.
3. **Diff** (`differ.diff_snapshots`) — Compares two lists of `ModelRow` to detect new models, deleted models, date changes, and models deprecating within 90 days.
4. **Feed** (`tools.generate_feed`) — Writes the changes to `feed.json` as a JSON Feed 1.1, merging with existing history.

### Project structure

| File | Purpose |
|---|---|
| `parser.py` | Markdown table → `ModelRow` records |
| `differ.py` | Deterministic snapshot diff |
| `tools.py` | Fetch, feed generation, pipeline orchestration |
| `storage.py` | Abstraction to read/write from local `data/` or a GCS bucket |
| `main.py` | CLI entry point with human-readable output |
| `deploy.sh` | Infrastructure-as-code script for GCP deployment |
| `Dockerfile` | Container definition for Cloud Run |
