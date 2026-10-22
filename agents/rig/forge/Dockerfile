# syntax=docker/dockerfile:1
FROM node:22.21.0-bookworm-slim AS node
FROM python:3.12.12-slim-bookworm AS runtime
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
    apt-get install -y --no-install-recommends ca-certificates libgl1 libegl1 libglib2.0-0 \
      libx11-6 libxi6 libxrender1 libxfixes3 libxxf86vm1 libxkbcommon0 libsm6 libgomp1; \
    python -m pip install --no-cache-dir --require-hashes -r requirements.lock -r requirements-test.lock; \
    python install_tools.py /opt/forge-tools; \
    node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci --strict-ssl=true --no-audit --no-fund; \
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
