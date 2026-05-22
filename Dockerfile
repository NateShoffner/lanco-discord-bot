FROM python:3.10-slim-bookworm

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libcairo2 && \
    rm -rf /var/lib/apt/lists/*

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY app/ app/
COPY assets/ assets/
COPY migrate.py .
COPY migrations/ migrations/

CMD ["sh", "-c", "python migrate.py && python app/main.py"]