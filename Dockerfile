FROM python:3.10-slim AS base

# ---------- install Poetry (cached layer) ----------
ENV POETRY_VERSION=1.7.1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION \
    && ln -s $POETRY_HOME/bin/poetry /usr/local/bin/poetry

ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app

# ---------- install Python dependencies ----------
# Copy only the files that affect dependency resolution first for better caching
COPY pyproject.toml poetry.lock* /app/

RUN poetry install --only main --no-interaction --no-ansi

# ---------- copy project source ----------
COPY . /app

# ---------- runtime configuration ----------
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"] 