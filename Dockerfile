FROM node:24-bookworm-slim AS frontend
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --registry="${NPM_REGISTRY}"
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/backend/.venv/bin:$PATH" \
    PREG_DATA_DIR=/data \
    PIP_INDEX_URL="${PIP_INDEX_URL}" \
    UV_INDEX_URL="${PIP_INDEX_URL}"

WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN pip install --no-cache-dir uv==0.6.16 \
    && if [ "${PIP_INDEX_URL}" != "https://pypi.org/simple" ]; then uv lock; fi \
    && uv sync --locked --no-dev \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app \
    && install -d -o app -g app -m 0700 /data
COPY backend/ ./
COPY --from=frontend /build/dist /srv/frontend/dist

USER app
EXPOSE 8000
CMD ["sh", "-c", "umask 077 && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --no-access-log --timeout-graceful-shutdown 5"]
