# syntax=docker/dockerfile:1
FROM node:22.23.4-bookworm-slim@sha256:ea11b74b986d520137cdef9a5346e447a00f275ecc4abc0055b7151226231e09 AS node
FROM python:3.12.15-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0 AS runtime
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
WORKDIR /app/forge
COPY . /app/forge/
RUN --mount=type=secret,id=system_ca \
    --mount=type=secret,id=proxy_ca \
    set -eu; \
    if [ -s /run/secrets/system_ca ]; then export SSL_CERT_FILE=/run/secrets/system_ca PIP_CERT=/run/secrets/system_ca; fi; \
    if [ -s /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates=20250419~deb12u2 libgl1=1.6.0-1 libegl1=1.6.0-1 libglib2.0-0=2.74.6-2+deb12u9 \
      libx11-6=2:1.8.4-2+deb12u2 libxi6=2:1.8-1+b1 libxrender1=1:0.9.10-1.1 libxfixes3=1:6.0.0-2 libxxf86vm1=1:1.1.4-1+b2 libxkbcommon0=1.5.0-1 libsm6=2:1.2.3-1 libgomp1=12.2.0-14+deb12u1; \
    python -m pip install --no-cache-dir --require-hashes -r requirements.lock -r requirements-test.lock; \
    python install_tools.py /opt/forge-tools; \
    node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci --ignore-scripts --strict-ssl=true --no-audit --no-fund; \
    rm -rf /var/lib/apt/lists/* /root/.npm /opt/forge-tools/archives; \
    useradd --uid 1000 --create-home forge; \
    mkdir -p /data; chown forge:forge /data; chmod -R a+rX /app/forge /opt/forge-tools
ENV PATH=/opt/forge-tools/bin:/app/forge/node_modules/.bin:$PATH \
    PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 RIG_FORGE_TOOL_ROOT=/app/forge
WORKDIR /app
USER forge
CMD ["uvicorn", "forge.service:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log", "--no-proxy-headers"]

FROM runtime AS test
