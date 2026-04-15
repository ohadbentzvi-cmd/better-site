# BetterSite worker service.
#
# This image runs `python -m pipeline.deploy`, which registers every flow
# deployment with the Prefect server (PREFECT_API_URL) and then serves runs
# in-process. Scale = more replicas of this service on Railway.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for psycopg + Playwright/lxml builds at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching. Both pipeline/ and api/
# requirements — the api service imports pipeline.* models, and the worker
# image is reused by the api service (separate Railway service, same Dockerfile).
COPY pipeline/requirements.txt /app/pipeline/requirements.txt
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install -r /app/pipeline/requirements.txt -r /app/api/requirements.txt

# Playwright browser binaries + system deps. Needed by the Scanner agent.
# Adds ~400MB but is cached as its own layer so we only pay the cost on
# Playwright-version bumps.
RUN playwright install --with-deps chromium

# Copy the rest of the repo. Flow code lives under pipeline/.
COPY . /app

CMD ["python", "-m", "pipeline.deploy"]
