# Build context is the repo root (uv workspace): docker build -f services/calculation/Dockerfile .

FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.12-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so source edits don't bust this layer.
COPY pyproject.toml uv.lock ./
COPY services/calculation/pyproject.toml services/calculation/
RUN uv sync --locked --package overcalc-calculation --no-dev --no-install-workspace

COPY services/calculation/src services/calculation/src
RUN uv sync --locked --package overcalc-calculation --no-dev --no-editable

FROM python:3.12-slim AS runtime
RUN useradd --system --uid 10001 --no-create-home overcalc
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER overcalc
EXPOSE 8000
CMD ["uvicorn", "overcalc_calculation.presentation.main:app_factory", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
