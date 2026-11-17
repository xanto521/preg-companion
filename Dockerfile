FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/backend/.venv/bin:$PATH" \
    PREG_DATA_DIR=/data

WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv==0.6.16 \
    && uv sync --locked --no-dev \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && install -d -o app -g app -m 0700 /data
COPY backend/ ./
COPY --from=frontend /build/dist /srv/frontend/dist

USER app
EXPOSE 8000
CMD ["sh", "-c", "umask 077 && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --no-access-log --timeout-graceful-shutdown 5"]
