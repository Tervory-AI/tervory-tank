#!/bin/sh
# Root inside this container only long enough to install the firewall.
# The coding process is an unprivileged user and cannot change those rules.
# On the host this container is rootless podman: container root is not host root.
# Every early exit says why on stderr: the service logs the container's stderr on failure.
set -eu
if ! python3 -m workers.egress_apply; then
  echo "worker task: firewall install failed; the task will not run" >&2
  exit 1
fi
if [ -f /run/secrets/tank_key ]; then
  # The secret files are written without a trailing newline (workers/secrets_io.py), so `read`
  # returns 1 at end of file even though it read the whole value. Judge by the value instead.
  OPENAI_API_KEY=""
  IFS= read -r OPENAI_API_KEY < /run/secrets/tank_key || true
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "worker task: /run/secrets/tank_key is empty or unreadable" >&2
    exit 1
  fi
  export OPENAI_API_KEY
fi
export OPENAI_API_BASE="${OPENAI_API_BASE:-http://127.0.0.1:8765/v1}"
exec setpriv --reuid=worker --regid=worker --init-groups --inh-caps=-all \
  python3 -m workers.task
