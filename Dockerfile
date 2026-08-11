# syntax=docker/dockerfile:1

# HermClaw — Multi-stage Docker Build
# Supports: Linux amd64/arm64

# ── Stage 1: Build ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY hermclaw/ hermclaw/

RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install s6-overlay for process supervision
ARG S6_OVERLAY_VERSION=3.2.0.0
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && rm /tmp/s6-overlay-noarch.tar.xz

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Create non-root user
RUN useradd -m -s /bin/bash hermclaw
USER hermclaw
WORKDIR /home/hermclaw

# Create default directories
RUN mkdir -p .hermclaw/sessions .hermclaw/skills .hermclaw/plugins .hermclaw/logs

# s6 service definitions
COPY --chown=hermclaw:hermclaw deploy/s6/ /etc/s6-overlay/s6-rc.d/

ENV HERMCLAW_STATE_DIR=/home/hermclaw/.hermclaw
EXPOSE 8765 8080

ENTRYPOINT ["/init"]
CMD ["hermclaw", "serve"]
