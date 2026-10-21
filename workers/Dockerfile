# The worker service. Task containers are a second image, built with podman at start.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/opt/tervory \
    HOME=/home/worker \
    XDG_RUNTIME_DIR=/run/user/1000

RUN apt-get update && apt-get install -y --no-install-recommends \
        podman fuse-overlayfs uidmap slirp4netns iptables nftables git ca-certificates openssl util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin worker

COPY workers/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY workers /opt/tervory/workers
COPY workers/storage.conf /home/worker/.config/containers/storage.conf
RUN chmod 755 /opt/tervory/workers/entrypoint.sh \
    && chown -R worker:worker /home/worker /opt/tervory

WORKDIR /opt/tervory
ENTRYPOINT ["/opt/tervory/workers/entrypoint.sh"]
