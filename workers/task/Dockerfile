# One sealed computer: Python, Node 22, Chromium via Playwright, and Aider.
# The repo is cloned at run time. No keys are baked into this image.
FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONPATH=/opt/tervory \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 git=1:2.39.5-0+deb12u3 ca-certificates=20250419~deb12u2 nftables=1.0.6-2+deb12u2 openssl=3.0.22-1~deb12u1 util-linux=2.38.1-5+deb12u3 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && useradd --create-home --uid 1001 --shell /usr/sbin/nologin worker

COPY workers/task/requirements.lock /tmp/requirements.lock
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r /tmp/requirements.lock \
    && playwright install --with-deps chromium \
    && rm /tmp/requirements.lock

COPY workers /opt/tervory/workers
RUN chmod 755 /opt/tervory/workers/task/entrypoint.sh

WORKDIR /work
ENTRYPOINT ["/opt/tervory/workers/task/entrypoint.sh"]
