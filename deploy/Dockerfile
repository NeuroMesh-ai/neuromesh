# UnityBrain Dockerfile — Production-ready, non-root, hardened
# Build: docker build -t unitybrain/server:latest .
# Run:  docker compose up -d

FROM python:3.11-slim AS base

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early
RUN groupadd -r unitybrain && \
    useradd -r -m -d /data -g unitybrain -s /sbin/nologin unitybrain

# Install UnityBrain
COPY . /opt/unitybrain/
RUN pip install --no-cache-dir --prefer-binary /opt/unitybrain

# Data volume
VOLUME /data

# Ports: 8080 (private API), 8090 (public mesh)
EXPOSE 8080 8090

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8080/api/ping || exit 1

# Run as non-root user
USER unitybrain

# Default config path
ENV UNITYBRAIN_CONFIG=/data/config.json
ENV UNITYBRAIN_DATA_DIR=/data
ENV OLLAMA_HOST=host.docker.internal:11434

WORKDIR /data

ENTRYPOINT ["tini", "--"]
CMD ["unitybrain", "serve", "--config", "/data/config.json"]