# Swarm-It Sidecar - Production Container
# Includes yrsn + PyTorch for full RSCT support
#
# Build: ./scripts/build-container.sh
# Run:   docker run -p 8080:8080 -e OPENAI_API_KEY=sk-... swarmit-api

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only first (smaller image)
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy sidecar code
COPY . /app/

# yrsn will be copied by build script to /app/yrsn
# Set Python path
ENV PYTHONPATH=/app
ENV YRSN_SRC=/app
ENV PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with uvicorn
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
