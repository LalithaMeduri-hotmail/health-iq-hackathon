# Health IQ backend (FastAPI). Build context is the REPO ROOT, not backend/, because the app
# reads catalogs and demo fixtures from <root>/data via Path(__file__).parents[3].
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv/backend \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# unixodbc is what pyodbc links against; without it `import pyodbc` fails even though the Azure
# SQL path is unused. curl is the container health probe.
RUN apt-get update \
    && apt-get install -y --no-install-recommends unixodbc curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /usr/local/bin/uv

WORKDIR /srv/backend

# Dependency layer first so application edits do not invalidate the install.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY backend/tests/fixtures ./tests/fixtures
COPY data /srv/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
