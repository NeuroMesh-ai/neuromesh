FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copy project
WORKDIR /app
COPY . /app/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install project
RUN pip install -e .

# Download default models (optional - comment out if not needed)
RUN ollama pull SmolLM2:1.7b || true

# Create non-root user
RUN useradd -m -u 1000 unitybrain && \
    chown -R unitybrain:unitybrain /app

USER unitybrain

# Expose ports
EXPOSE 8080 9999

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Default command
CMD ["python", "-m", "src.unitybrain_v3_final"]