# syntax=docker/dockerfile:1
#
# FantasyGM Lab — shared application image for self-hosted deployment.
#
# Why one image for four services (not four separate Dockerfiles):
# every real (non-cron) service in render.yaml — fantasygm-lab (Streamlit),
# fantasygm-lab-mobile-api, fantasygm-lab-stripe-webhook, and
# fantasygm-lab-revenuecat-webhook — shares the exact same runtime
# (Python 3.12.10), the exact same dependency set (requirements.txt), and
# the exact same buildCommand (`pip install -r requirements.txt`; the
# Streamlit service additionally runs the deterministic, network-free
# prepare_public_player_cache.py, which is harmless to run for every
# service, so it's baked into the shared image rather than forked into a
# separate build). The four services differ only in their startCommand
# (see docker-compose.yml's `command:` override per service), exactly as
# they do in render.yaml. One image means one build, one set of layers to
# cache/scan/patch, and a self-hosted box that only has to pull/rebuild one
# thing when a dependency changes — the 4-Dockerfile alternative would just
# duplicate the same builder stage four times for zero practical benefit at
# this scale.
#
# Multi-stage: the "builder" stage compiles/installs Python dependencies
# (some of which need build tooling, e.g. wheels with native extensions)
# into an isolated venv; the final stage copies only that venv plus the
# application source into a slim runtime image, so none of the build
# toolchain (gcc, headers, pip's wheel cache, etc.) ends up in the image
# that actually runs in production.

ARG PYTHON_VERSION=3.12.10

# ---------------------------------------------------------------------------
# Stage 1: builder — install Python dependencies into a self-contained venv.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

# Build tooling for any dependency that needs to compile a native extension.
# Not present in the final image (this stage is discarded).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV VENV_PATH=/opt/venv
RUN python -m venv "$VENV_PATH"
ENV PATH="$VENV_PATH/bin:$PATH"

WORKDIR /build
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image with only the venv + application code.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# curl is used by the docker-compose healthchecks (hitting each service's
# own /health or /_stcore/health endpoint, same paths Render's own health
# checks already use — see render.yaml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

ENV VENV_PATH=/opt/venv
ENV PATH="$VENV_PATH/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application source. See .dockerignore for what's intentionally excluded
# (the mobile/ Expo app, tests/, docs/, local dev-only state, etc.) — none
# of that is needed to run any of the four web services.
COPY . .

# Mirrors render.yaml's fantasygm-lab (Streamlit) buildCommand step:
#   pip install -r requirements.txt && python scripts/prepare_public_player_cache.py
# This script only reads checked-in SQLite/JSON/CSV inputs (no network
# calls — see its own module docstring) and is idempotent, so it's safe to
# always run here even for the three services that don't strictly need its
# output; that keeps this Dockerfile identical for all four services.
RUN python scripts/prepare_public_player_cache.py

RUN chown -R appuser:appuser /app
USER appuser

# Informational only — the actual bound port is $PORT, supplied per-service
# by docker-compose.yml so it matches each service's render.yaml entry.
EXPOSE 8080

# No default CMD: docker-compose.yml sets the exact startCommand for each
# of the four services (copied verbatim from render.yaml), the same way
# Render's dashboard runs one startCommand per service from one repo.
