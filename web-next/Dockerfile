# syntax=docker/dockerfile:1
#
# FantasyGM Lab — web-next (Next.js) image for self-hosted deployment.
#
# Separate from the root `Dockerfile`: that one builds the four Python
# services (Streamlit + FastAPI) from one shared image; this is a Node/
# Next.js app with its own runtime, dependency set, and build step
# (`npm ci && npm run build`), so it gets its own image entirely rather
# than being forced into the Python multi-service image. Node 22 matches
# `.github/workflows/ci.yml`'s `web-next` job (`actions/setup-node@v4`,
# `node-version: "22"`), so what's verified in CI is the same runtime this
# image ships.
#
# IMPORTANT — NEXT_PUBLIC_* vars are compile-time, not runtime: Next.js
# statically inlines every `process.env.NEXT_PUBLIC_*` reference into the
# client JS bundle during `next build` (see src/lib/env.ts). Unlike the
# Python services (which read `.env` at container *runtime* via
# docker-compose's `env_file:`), these four vars must be passed as Docker
# build args — wired through docker-compose.yml's `build.args` the same
# way DYNASTYGM_BUILD/DYNASTYGM_DEPLOYED_AT already reach the root
# Dockerfile — so they are baked into this image's `.next` output at
# `docker compose build` time. Changing one of them after the fact
# requires a rebuild, not just a container restart / `.env` edit.
#
# Multi-stage, mirroring the root Dockerfile's builder/runtime split:
#   1. deps     — installs the FULL dependency set (including
#                 devDependencies: typescript, tailwindcss, the
#                 @tailwindcss/turbopack loader) because `next build` needs
#                 them.
#   2. builder  — copies those deps + the app source, bakes in the four
#                 NEXT_PUBLIC_* build args, runs `next build`.
#   3. prod-deps — installs ONLY production dependencies (next, react,
#                 react-dom, @supabase/supabase-js) into a separate,
#                 smaller node_modules — this is what actually ships.
#   4. runtime  — slim image with just prod node_modules + the built
#                 `.next` output + `public/` + `package.json`, running
#                 as a non-root user, same as the root Dockerfile's
#                 runtime stage.

ARG NODE_VERSION=22-slim

# ---------------------------------------------------------------------------
# Stage 1: deps — full install (incl. devDependencies) for the build step.
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS deps
WORKDIR /build
# .npmrc carries legacy-peer-deps=true (see web-next/.npmrc) — `npm ci`
# reads it automatically from the working directory.
COPY web-next/package.json web-next/package-lock.json web-next/.npmrc ./
RUN npm ci

# ---------------------------------------------------------------------------
# Stage 2: builder — build the production Next.js output.
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder
WORKDIR /build
COPY --from=deps /build/node_modules ./node_modules
COPY web-next/ ./

# Baked into the client bundle at build time — see this file's header
# comment. Real values come from docker-compose.yml's `build.args` (which
# itself reads them from `.env` via Compose's ${VAR} interpolation, same
# mechanism as .env.example documents for every other var).
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_STREAMLIT_BASE_URL
ENV NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY} \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_STREAMLIT_BASE_URL=${NEXT_PUBLIC_STREAMLIT_BASE_URL}

RUN npm run build
# Guarantees the final stage's `COPY --from=builder /build/public` below
# never fails even on a revision of this app that has no public/ dir yet
# (there isn't one as of this writing) — Docker COPY errors on a missing
# source path.
RUN mkdir -p public

# ---------------------------------------------------------------------------
# Stage 3: prod-deps — production-only dependencies (no devDependencies).
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS prod-deps
WORKDIR /build
COPY web-next/package.json web-next/package-lock.json web-next/.npmrc ./
RUN npm ci --omit=dev

# ---------------------------------------------------------------------------
# Stage 4: runtime — slim image, only what's needed to run `next start`.
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runtime

# curl is used by docker-compose's healthcheck (hitting this service's own
# root path), same convention as the root Dockerfile's Python services.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10002 --shell /usr/sbin/nologin webnextuser

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY --from=prod-deps /build/node_modules ./node_modules
COPY --from=builder /build/package.json ./package.json
COPY --from=builder /build/next.config.ts ./next.config.ts
COPY --from=builder /build/.next ./.next
COPY --from=builder /build/public ./public

RUN chown -R webnextuser:webnextuser /app
USER webnextuser

# Informational only — the actual bound port is $PORT, supplied at runtime
# by docker-compose.yml (`next start` reads `PORT` from its process
# environment directly, unlike the Python services' `--port` CLI flags, so
# no `sh -c`/`$$PORT` shell-expansion trick is needed here).
EXPOSE 8080

CMD ["npm", "run", "start"]
