# MedAI backend image. Build from the MedAI folder (the AI package is shared):
#   docker build -f backend/Dockerfile -t medai-backend .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/medai

# Set INSTALL_AI=true to include PyTorch + TorchXRayVision (CPU, adds ~1 GB).
ARG INSTALL_AI=false
COPY backend/requirements.txt backend/requirements-ai.txt backend/
RUN pip install -r backend/requirements.txt \
 && if [ "$INSTALL_AI" = "true" ]; then pip install -r backend/requirements-ai.txt; fi

COPY ai/ ai/
COPY backend/ backend/
RUN useradd --create-home --uid 10001 medai \
 && mkdir -p /data/xrays && chown -R medai /data /srv/medai
USER medai
WORKDIR /srv/medai/backend

ENV UPLOAD_DIR=/data/xrays
# Only trust X-Forwarded-For from these proxy addresses (uvicorn reads this variable). Set it to your
# load balancer's address; never "*" when the container is reachable directly, or clients could spoof
# their IP and bypass rate limits.
ENV FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000
# Apply migrations, then serve. Weights are mounted at runtime (never baked into the image).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
