# Hermes Agent v0.20.0 (v2026.8.3) - Production Dockerfile for Runflare Free
# Builds Hermes from source using uv, runs gateway in foreground
#
# Build:    docker build -t hermes-gate .
# Run:      docker run --rm -it -p 8000:8000 -v hermes-data:/opt/data -e TELEGRAM_BOT_TOKEN=xxx -e TELEGRAM_ALLOWED_USERS=xxx hermes-gate

FROM python:3.12-slim AS builder

# System dependencies for building Hermes and runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (pinned version matching Hermes v0.20.0 bootstrap)
ENV UV_VERSION=0.12.3
RUN curl -LsSf https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz \
    | tar -xz -C /usr/local/bin --strip-components=1 uv-x86_64-unknown-linux-gnu/uv \
    && chmod +x /usr/local/bin/uv

# Hermes installation directory
ENV HERMES_HOME=/opt/hermes
ENV HERMES_AGENT_DIR=${HERMES_HOME}/hermes-agent

# Clone Hermes Agent at exact v0.20.0 tag (v2026.8.3)
ARG HERMES_TAG=v2026.8.3
ARG HERMES_REPO=https://github.com/NousResearch/hermes-agent.git

RUN git clone --depth 1 --branch ${HERMES_TAG} ${HERMES_REPO} ${HERMES_AGENT_DIR}

WORKDIR ${HERMES_AGENT_DIR}

# Install Hermes with uv (uses uv.lock from the tagged release)
# The exclude-newer issue in v0.20.0 is fixed in the tagged uv.lock via exclude-newer-package exemptions
RUN uv sync --frozen --no-dev --no-editable

# Runtime stage - minimal image
FROM python:3.12-slim AS runtime

# Runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 hermes

# Copy uv from builder
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv

# Copy Hermes installation
ENV HERMES_HOME=/opt/hermes
ENV HERMES_AGENT_DIR=${HERMES_HOME}/hermes-agent
COPY --from=builder ${HERMES_AGENT_DIR} ${HERMES_AGENT_DIR}

# Create data directory for persistent state (mounted volume)
RUN mkdir -p /opt/data && chown -R hermes:hermes /opt/data /opt/hermes

# Switch to non-root user
USER hermes
WORKDIR /opt/data

# Environment for Hermes runtime
ENV PATH="${HERMES_AGENT_DIR}/.venv/bin:${PATH}"
ENV HERMES_HOME=/opt/data
ENV HERMES_GATEWAY_NO_SUPERVISE=1

# Expose gateway API/health port (optional for chat-only, but Runflare requires a port)
EXPOSE 8000

# Health check - Hermes gateway doesn't have HTTP health endpoint by default in polling mode
# We'll use a simple process check instead
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD pgrep -f "hermes gateway run" || exit 1

# Run gateway in foreground (required for Docker/Runflare)
ENTRYPOINT ["hermes", "gateway", "run"]