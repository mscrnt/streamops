# Multi-stage build for StreamOps

# Stage 1: Build UI
FROM node:20-alpine AS ui-builder

WORKDIR /build

# Copy UI package files
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Copy UI source and build
COPY app/ui ./app/ui
COPY tailwind.config.js postcss.config.js vite.config.js ./
# Build UI
RUN npm run build

# Stage 2: NVIDIA CUDA base with Python and dependencies
FROM nvidia/cuda:12.9.0-cudnn-runtime-ubuntu22.04 AS base

# Set non-interactive mode and timezone
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install Python 3.11 and system dependencies
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get update && apt-get install -y --no-install-recommends \
    # Add repository for Python 3.11
    software-properties-common \
    wget \
    curl \
    xz-utils \
    sqlite3 \
    gcc \
    g++ \
    procps \
    tzdata \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    # Python 3.11
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    python3.11-distutils \
    python3-pip \
    # FFmpeg with CUDA support
    ffmpeg \
    # Additional media libraries
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libx264-dev \
    libx265-dev \
    nvidia-cuda-toolkit \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Install pip for Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Install NATS server
RUN wget -O /tmp/nats.tar.gz https://github.com/nats-io/nats-server/releases/download/v2.10.24/nats-server-v2.10.24-linux-amd64.tar.gz \
    && tar -xzf /tmp/nats.tar.gz -C /usr/local/bin --strip-components=1 \
    && rm /tmp/nats.tar.gz \
    && chmod +x /usr/local/bin/nats-server

# Install s6-overlay for process supervision
ARG S6_OVERLAY_VERSION=3.2.0.2
RUN wget -O /tmp/s6-overlay-noarch.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz \
    && wget -O /tmp/s6-overlay-x86_64.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-x86_64.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-x86_64.tar.xz \
    && rm /tmp/s6-overlay-*.tar.xz

# Set up Python environment
WORKDIR /opt/streamops

# Copy and install Python dependencies
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Copy s6 service configurations (using legacy format for better compatibility)
COPY app/pkg/services.d /etc/services.d/
COPY app/pkg/cont-init.d /etc/cont-init.d/

# Make all scripts executable
RUN chmod +x /etc/services.d/*/run /etc/cont-init.d/* 2>/dev/null || true

# Copy built UI from stage 1
COPY --from=ui-builder /build/app/ui/dist ./app/static

# Create necessary directories
RUN mkdir -p /data/db /data/logs /data/cache /data/thumbs /data/config \
    && mkdir -p /var/lib/streamops/nats /var/log/streamops \
    && chmod 755 /var/lib/streamops /var/log/streamops

# Environment variables
ENV PYTHONPATH=/opt/streamops \
    ROLE=all \
    NATS_ENABLE=true \
    DB_PATH=/data/db/streamops.db \
    CACHE_DIR=/data/cache \
    THUMBS_DIR=/data/thumbs \
    LOG_DIR=/data/logs \
    CONFIG_PATH=/data/config/config.json \
    S6_KEEP_ENV=1 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=2

# Ports
EXPOSE 7767 7768 7769

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7767/health/live || exit 1

# Volume for persistent data
VOLUME ["/data"]

# Entry point with s6-overlay
ENTRYPOINT ["/init"]