#!/bin/sh
# Root inside this container only long enough to install the firewall.
# The coding process is an unprivileged user and cannot change those rules.
# On the host this container is rootless podman: container root is not host root.
set -eu
python3 -m workers.egress_apply || exit 1
if [ -f /run/secrets/tank_key ]; then
  IFS= read -r OPENAI_API_KEY < /run/secrets/tank_key || exit 1
  export OPENAI_API_KEY
fi
export OPENAI_API_BASE="${OPENAI_API_BASE:-http://127.0.0.1:8765/v1}"
exec setpriv --reuid=worker --regid=worker --init-groups --inh-caps=-all \
  python3 -m workers.task
