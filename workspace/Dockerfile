# Multi-stage build; output: standalone keeps the runtime image small.
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# Coolify injects build-time variables into every stage. NODE_ENV=production
# makes npm skip devDependencies. Next then installs the newest TypeScript
# (7.x), which cannot load next.config.ts. --include=dev keeps the pinned 5.9.3.
RUN npm install --include=dev --no-audit --no-fund

# Self-hosted CLI release (served as /cli/): built here from the cli/ package, never
# committed (review of #506, should-fix 4). `cli` is a named build context:
# docker-compose.yml sets additional_contexts.cli=./cli; by hand:
#   docker build --build-context cli=cli -f workspace/Dockerfile workspace
# The build is reproducible on a given host (fixed mtimes and modes, sorted tar, gzip -n, npm ci from the lockfile).
FROM node:22-slim AS cli-release
WORKDIR /src
COPY --from=cli . ./cli
RUN node cli/scripts/build-release.mjs --out /out/cli

# Just the release files, for CI to compare against a direct build (--target cli-files).
FROM scratch AS cli-files
COPY --from=cli-release /out/cli /

FROM node:22-slim AS build
WORKDIR /app
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
# Sign-in and sign-up happen on our own domain, not Clerk's hosted accounts page.
# These are route paths, not secrets, so they are fixed here.
ENV NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in \
    NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up \
    NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/ \
    NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/
COPY --from=deps /app/node_modules ./node_modules
COPY . .
COPY --from=cli-release /out/cli ./public/cli
RUN npm run build

FROM node:22-slim AS run
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
RUN groupadd -r app && useradd -r -g app app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER app
EXPOSE 3000
CMD ["node", "server.js"]
