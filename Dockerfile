# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MORPHEUS_WEB_DIST=/opt/morpheus/frontend/dist \
    MORPHEUS_STATE_DIR=/data \
    HOME=/home/morpheus

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin morpheus

WORKDIR /opt/morpheus
COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-build /src/frontend/dist/ frontend/dist/
RUN mkdir -p /data \
    && chown -R morpheus:morpheus /data /home/morpheus

WORKDIR /opt/morpheus/backend
EXPOSE 8000
VOLUME ["/data"]

USER morpheus

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()" || exit 1

# Do not trust arbitrary Forwarded/X-Forwarded-* headers by default. Deployments
# behind a trusted reverse proxy should configure that boundary explicitly at the
# edge instead of letting internet clients choose their apparent source address.
CMD ["python", "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
