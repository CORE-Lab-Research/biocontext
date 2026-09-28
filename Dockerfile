# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BIOCONTEXT_CACHE_PATH=/data/biocontext_cache.db

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable dependency management
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

# Copy dependency specifications first for layer caching
COPY pyproject.toml README.md ./

# Install python dependencies without the project first
RUN uv pip install --system -r pyproject.toml

# Copy project source code
COPY src/ ./src/

# Install biocontext package
RUN uv pip install --system -e .

# Create cache data directory
RUN mkdir -p /data

VOLUME ["/data"]

EXPOSE 8000

# Default entrypoint runs the MCP server via stdio
ENTRYPOINT ["biocontext"]
CMD ["serve"]
