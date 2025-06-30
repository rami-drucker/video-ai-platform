# Use CUDA base image if GPU is enabled, otherwise use slim
ARG USE_GPU=false
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 as gpu-base
FROM python:3.11-slim as cpu-base

# Select the base image based on USE_GPU arg
FROM ${USE_GPU:-false} as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# If GPU is enabled, install PyTorch with CUDA support
RUN if [ "$USE_GPU" = "true" ] ; then \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 ; \
    fi

# Copy application code
COPY ./app .

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
