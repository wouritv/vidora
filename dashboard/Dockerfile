# Production image: builds a real `vite build` static bundle and serves it
# with nginx. For local development with hot reload, see Dockerfile.dev
# (used by the root docker-compose.yml) instead.
#
# This used to just run `npm run dev` in production too, which shipped
# Vite's dev-only HMR client (its WebSocket can't resolve a port behind a
# reverse proxy -- "wss://localhost:undefined") and served some
# dependencies' worker/module chunks as blob-URL <script> elements, which
# the CSP's script-src (index.html; no 'unsafe-inline', no blob:) correctly
# refused to load. A real production build emits neither: no HMR client,
# and worker/module chunks as real same-origin hashed files.

# ============================================================
# Stage 1: build the static production bundle
# ============================================================
FROM node:22-alpine AS builder

WORKDIR /app

ARG VITE_SUPABASE_URL=http://localhost:3000
ARG VITE_SUPABASE_ANON_KEY=supabase_key
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ============================================================
# Stage 2: serve the built static files with nginx
# ============================================================
# nginxinc/nginx-unprivileged: same nginx image, pre-configured to listen
# on a high port and run as a non-root user out of the box (audit finding
# H14 -- avoid running any of this app's containers as root), unlike the
# stock nginx image which needs its own manual USER/permission setup to do
# the same thing.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
