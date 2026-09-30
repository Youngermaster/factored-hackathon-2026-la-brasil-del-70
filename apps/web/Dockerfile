# syntax=docker/dockerfile:1.7
# Production web image, built from the repository root:
#   docker build -f apps/web/Dockerfile --build-arg VITE_DEMO_MODE=true -t bank-agent-web .
#
# The SPA is built with Vite in a Node stage; the runtime is Caddy alone, serving the static files with a strict
# CSP and reverse-proxying /v1 and /health to the API (deploy/caddy/Caddyfile). Caddy itself is compiled from
# deploy/caddy/module (the standard distribution, 2.11.4) with a current Go toolchain and pinned module versions,
# because the official binary carries fixed-upstream vulnerabilities in the Go standard library and golang.org/x.
# The binary has no file capabilities, so it starts under cap_drop ALL and no-new-privileges as a non-root user; it
# binds 80 and 443 through the namespaced sysctl net.ipv4.ip_unprivileged_port_start set in deploy/compose.prod.yml.
# VITE_DEMO_MODE=true shows the demo persona picker (the public demo; docs/security/demo-mode.md).

ARG NODE_IMAGE=node:24.21.0-alpine3.24@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1
ARG CADDY_IMAGE=caddy:2.11.4-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b
ARG GO_IMAGE=golang:1.26.8-alpine3.24@sha256:8ac98ca534ac3f51e1f420a1dd2c15e74c75cfa0f23f3ad27eb5d7236c349a0c

FROM ${GO_IMAGE} AS caddy-build
ENV CGO_ENABLED=0 \
    GOFLAGS=-mod=readonly
WORKDIR /src
COPY deploy/caddy/module/go.mod deploy/caddy/module/go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY deploy/caddy/module/main.go ./
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -trimpath -ldflags "-s -w" -o /out/caddy . && /out/caddy version

FROM ${NODE_IMAGE} AS build
ENV COREPACK_HOME=/opt/corepack \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    CI=true
RUN corepack enable pnpm && corepack install -g pnpm@10.33.0
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
COPY apps/web/ ./
ARG VITE_DEMO_MODE=false
ENV VITE_DEMO_MODE=${VITE_DEMO_MODE}
# Source maps stay out of the public image.
RUN pnpm run build && find dist -name '*.map' -delete

FROM ${CADDY_IMAGE} AS web
RUN addgroup -S -g 10002 caddy && adduser -S -D -H -u 10002 -G caddy -s /sbin/nologin caddy \
    && mkdir -p /data/caddy /config/caddy && chown -R caddy:caddy /data /config
# Replaces the official binary (which also carries cap_net_bind_service, not grantable under cap_drop ALL).
COPY --from=caddy-build /out/caddy /usr/bin/caddy
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/web/dist /srv
USER 10002:10002
EXPOSE 80 443 443/udp
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8081/healthz"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
