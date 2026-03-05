FROM python:3.12-slim

# Prevent .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (system-wide, no venv needed in container)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY *.py ./

# Run the pipeline
CMD ["uv", "run", "--frozen", "--no-dev", "python", "main.py"]
