# Reviewer release: build React and serve it with FastAPI under one origin.
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY requirements.txt aereo-requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt -r aereo-requirements.txt
COPY app/ /srv/app/
COPY aereo/ /srv/aereo/
COPY --from=frontend-builder /frontend/dist/ /srv/frontend/dist/
RUN groupadd --system geoinsight && useradd --system --gid geoinsight --home-dir /srv geoinsight \
    && mkdir -p /data && chown -R geoinsight:geoinsight /data /srv
USER geoinsight
ENV AEREO_FRONTEND_DIR=/srv/frontend/dist \
    AEREO_DATABASE_URL=sqlite:////data/measurements.sqlite3
EXPOSE 8000
CMD ["uvicorn", "aereo.production:create_production_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
