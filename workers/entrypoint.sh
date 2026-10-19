#!/bin/sh
# The service process is the unprivileged user "worker" and runs rootless podman.
# Container root is used only to grant that user a subuid range on first start.
set -eu
if [ "$(id -u)" -eq 0 ]; then
  grep -q '^worker:' /etc/subuid 2>/dev/null || echo 'worker:100000:65536' >> /etc/subuid
  grep -q '^worker:' /etc/subgid 2>/dev/null || echo 'worker:100000:65536' >> /etc/subgid
  mkdir -p /run/user/1000 /var/lib/workers /home/worker/.config/containers
  chown -R worker:worker /run/user/1000 /var/lib/workers /home/worker
  chmod 700 /run/user/1000 /var/lib/workers
  exec setpriv --reuid=worker --regid=worker --init-groups \
    env HOME=/home/worker XDG_RUNTIME_DIR=/run/user/1000 python -m workers.service
fi
exec python -m workers.service
