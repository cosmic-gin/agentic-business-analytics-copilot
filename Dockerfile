FROM node:24-bookworm-slim AS frontend
WORKDIR /build
RUN npm install --global pnpm@11.25.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
RUN pnpm build

FROM python:3.12-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_MODE=demo \
    LLM_PROVIDER=none
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache
COPY backend/app ./backend/app
COPY scripts/generate_snapshot.py scripts/build_database.py ./scripts/
COPY data/metadata ./data/metadata
COPY data/snapshot ./data/snapshot
COPY evals/reports/demo-v1.json ./evals/reports/demo-v1.json
COPY --from=frontend /build/dist ./frontend/dist
RUN python -m scripts.build_database \
    && chmod 444 data/analytics.sqlite
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --no-access-log"]
