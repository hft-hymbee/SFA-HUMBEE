# syntax=docker/dockerfile:1
# Humbee SFA web (Next.js static export served by nginx). Build context: REPO ROOT (pnpm workspace)
#   docker build -f apps/web/Dockerfile \
#     --build-arg NEXT_PUBLIC_SFA_API_BASE_URL=https://api.example.com \
#     -t humbee-sfa-web .
#   docker run -p 8080:8080 humbee-sfa-web
FROM node:22-alpine AS build

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /repo

# Workspace manifests first so the install layer is cached.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY patches ./patches
COPY apps/web/package.json apps/web/package.json
COPY packages/api-contract/package.json packages/api-contract/package.json
COPY packages/design-tokens/package.json packages/design-tokens/package.json
COPY packages/eslint-config/package.json packages/eslint-config/package.json
COPY packages/humbee-design-system/package.json packages/humbee-design-system/package.json
COPY packages/tsconfig/package.json packages/tsconfig/package.json
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store --filter web...

COPY packages ./packages
COPY apps/web ./apps/web

# NEXT_PUBLIC_* is inlined at build time, so the API URL must be a build arg (one image per env).
ARG NEXT_PUBLIC_SFA_API_BASE_URL
ARG NEXT_PUBLIC_APP_VERSION=1.0.0
ENV NEXT_PUBLIC_SFA_API_BASE_URL=$NEXT_PUBLIC_SFA_API_BASE_URL \
    NEXT_PUBLIC_APP_VERSION=$NEXT_PUBLIC_APP_VERSION \
    NEXT_TELEMETRY_DISABLED=1
RUN test -n "$NEXT_PUBLIC_SFA_API_BASE_URL" || (echo "NEXT_PUBLIC_SFA_API_BASE_URL build arg is required" && exit 1)
RUN pnpm --filter web build && test -f apps/web/out/index.html


# Non-root nginx; listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
  listen 8080;
  root /usr/share/nginx/html;
  index index.html;
  server_tokens off;

  gzip on;
  gzip_types text/css application/javascript application/json image/svg+xml text/plain;

  add_header X-Content-Type-Options "nosniff" always;
  add_header X-Frame-Options "DENY" always;
  add_header Referrer-Policy "strict-origin-when-cross-origin" always;

  # Hashed build assets are immutable.
  location /_next/static/ {
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    add_header X-Content-Type-Options "nosniff" always;
    try_files $uri =404;
  }

  # HTML/RSC payloads must revalidate so a new deploy is picked up immediately.
  location / {
    add_header Cache-Control "no-cache" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    try_files $uri $uri.html $uri/index.html =404;
  }

  error_page 404 /404.html;
}
EOF

COPY --from=build /repo/apps/web/out /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
