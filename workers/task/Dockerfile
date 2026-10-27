# One sealed computer: Python, Node 22, Chromium via Playwright, and Aider.
# The repo is cloned at run time. No keys are baked into this image.
FROM node:22-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONPATH=/opt/tervory \
    PATH=/opt/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip git ca-certificates nftables openssl util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && useradd --create-home --uid 1001 --shell /usr/sbin/nologin worker

COPY workers/task/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && playwright install --with-deps chromium \
    && rm /tmp/requirements.txt

COPY workers /opt/tervory/workers
RUN chmod 755 /opt/tervory/workers/task/entrypoint.sh

WORKDIR /work
ENTRYPOINT ["/opt/tervory/workers/task/entrypoint.sh"]
