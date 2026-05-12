# NeuroMesh Dockerfile — Production-ready, non-root, hardened
# Build: docker build -t neuromesh/server:latest .
# Run:  docker compose up -d

FROM python:3.11-slim AS base

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early
RUN groupadd -r neuromesh && \
    useradd -r -m -d /data -g neuromesh -s /sbin/nologin neuromesh

# Install NeuroMesh
COPY . /opt/neuromesh/
RUN pip install --no-cache-dir --prefer-binary /opt/neuromesh

# Data volume
VOLUME /data

# Ports: 8080 (private API), 8090 (public mesh)
EXPOSE 8080 8090

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8080/api/ping || exit 1

# Run as non-root user
USER neuromesh

# Default config path
ENV NEUROMESH_CONFIG=/data/config.json
ENV NEUROMESH_DATA_DIR=/data
ENV OLLAMA_HOST=host.docker.internal:11434

WORKDIR /data

ENTRYPOINT ["tini", "--"]
CMD ["neuromesh", "serve", "--config", "/data/config.json"]