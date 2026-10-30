FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
# wget is the compose healthcheck. The homepage is the probe.
RUN apk add --no-cache wget && mkdir -p /data && chown node:node /data
COPY --from=build --chown=node:node /app/out ./out
COPY --from=build --chown=node:node /app/server.mjs ./server.mjs
COPY --from=build --chown=node:node /app/release-store.mjs ./release-store.mjs
USER node
EXPOSE 3000
# Serves the static site and POST /api/release-notice.
# Addresses append to /data/release-signups.jsonl (the site_signups volume).
CMD ["node", "server.mjs"]
