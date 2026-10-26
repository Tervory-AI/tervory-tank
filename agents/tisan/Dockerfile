FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY _chassis/requirements.lock .
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data /opt/npm-cache \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY tisan/app.py /app/app.py
COPY tisan/scaffold.py /app/scaffold.py
COPY tisan/figma.py /app/figma.py
COPY tisan/gold_sources.py /app/gold_sources.py
COPY tisan/review_store.py /app/review_store.py
COPY tisan/fixtures /app/fixtures
COPY tisan/templates /app/templates
# Node is for the scaffold checks. Dependencies are cached here so a run needs no network.
# Node 22 LTS, pinned to an exact patch. The hashes come from
# https://nodejs.org/dist/v22.23.4/SHASUMS256.txt; the build fails if the tarball does not match.
ARG NODE_VERSION=22.23.4
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates=20250419+deb13u1 curl=8.14.1-2+deb13u7 xz-utils=5.8.1-1+deb13u2 \
    && arch="$(uname -m)" \
    && case "$arch" in \
         x86_64) node_arch=x64; node_sha256=1805bcd35e6815559bd2eb97db438d3fdb0eb3a5e6a977b7c1badca76337e9ce ;; \
         aarch64) node_arch=arm64; node_sha256=6287aa46b6c375d816e63ae66d024fbbfd70404825aabdfdf898a970871d2f4b ;; \
         *) echo "unsupported architecture $arch" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" -o /tmp/node.tar.xz \
    && echo "${node_sha256}  /tmp/node.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && apt-get purge -y curl xz-utils \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/npm-warm \
    && cp /app/templates/next-site/package.json /app/templates/next-site/package-lock.json /tmp/npm-warm/ \
    && cd /tmp/npm-warm \
    && NEXT_TELEMETRY_DISABLED=1 PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
       npm ci --cache /opt/npm-cache --no-audit --no-fund \
    && rm -rf /tmp/npm-warm \
    && chown -R agent:agent /opt/npm-cache /data
USER agent
ENV AGENT_NAME=tisan \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    TISAN_TEMPLATE=/app/templates/next-site \
    TISAN_FIGMA_FIXTURE=/app/fixtures/tervory-landing.json \
    TISAN_NPM_CACHE=/opt/npm-cache \
    TISAN_NPM_OFFLINE=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
