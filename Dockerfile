# Hermes Agent v0.20.0 (v2026.8.3) - Runflare Free
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_VERSION=0.12.3
RUN curl -LsSf https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz \
    | tar -xz -C /usr/local/bin --strip-components=1 uv-x86_64-unknown-linux-gnu/uv \
    && chmod +x /usr/local/bin/uv

ENV HERMES_HOME=/opt/hermes
ENV HERMES_AGENT_DIR=/opt/hermes/hermes-agent

ARG HERMES_TAG=v2026.8.27
ARG HERMES_REPO=https://github.com/NousResearch/hermes-agent.git

RUN git clone --depth 1 --branch ${HERMES_TAG} ${HERMES_REPO} ${HERMES_AGENT_DIR}

WORKDIR ${HERMES_AGENT_DIR}

COPY patches/hermes-bale.patch /tmp/hermes-bale.patch
RUN git apply --check /tmp/hermes-bale.patch && git apply /tmp/hermes-bale.patch && rm /tmp/hermes-bale.patch

RUN uv sync --frozen --no-dev

FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    procps \
    libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 hermes

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /opt/hermes/hermes-agent /opt/hermes/hermes-agent
COPY bale-plugin /opt/hermes/bale-plugin
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh && mkdir -p /opt/data && \
    chown -R hermes:hermes /opt/data /opt/hermes

USER hermes
WORKDIR /opt/data

ENV HERMES_AGENT_DIR=/opt/hermes/hermes-agent
ENV PATH="${HERMES_AGENT_DIR}/.venv/bin:${PATH}"
ENV HERMES_HOME=/opt/data
ENV HERMES_GATEWAY_NO_SUPERVISE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "hermes gateway" || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
