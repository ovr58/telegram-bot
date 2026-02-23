FROM python:3.11-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/usr/src/app/.venv/bin:$PATH"

RUN useradd -m -r -s /usr/sbin/nologin appuser

WORKDIR /usr/src/app

RUN pip install --no-cache-dir uv Babel

COPY --chown=appuser:appuser pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --group bot --no-group admin --no-group dev

COPY --chown=appuser:appuser . .

RUN pybabel compile -d ./bot/locales -D messages --statistics || true

RUN mkdir -p /usr/src/app/logs \
    && chown -R appuser:appuser /usr/src/app/logs

USER appuser

CMD ["python", "-m", "bot"]
