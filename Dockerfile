FROM python:3.14-slim-bookworm AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libcairo2-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry && \
    poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main && \
    find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    /app/.venv/bin/pip uninstall -y pip setuptools 2>/dev/null || true


FROM python:3.14-slim-bookworm AS runtime

ARG GIT_COMMIT_HASH=unknown
ENV GIT_COMMIT_HASH=${GIT_COMMIT_HASH}

WORKDIR /app

# Only the runtime system library — not the dev headers
RUN apt-get update && \
    apt-get install -y --no-install-recommends libcairo2 && \
    rm -rf /var/lib/apt/lists/*

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Add the venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

COPY app/ app/
COPY assets/ assets/
COPY migrate.py .
COPY migrations/ migrations/
COPY pyproject.toml .

CMD ["sh", "-c", "python migrate.py && python app/main.py"]
