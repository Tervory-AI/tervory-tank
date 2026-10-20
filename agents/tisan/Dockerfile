FROM python:3.12-slim
WORKDIR /app
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
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
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
    && arch="$(uname -m)" \
    && case "$arch" in \
         x86_64) node_arch=x64 ;; \
         aarch64) node_arch=arm64 ;; \
         *) echo "unsupported architecture $arch" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-${node_arch}.tar.xz" -o /tmp/node.tar.xz \
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
