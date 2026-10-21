#!/bin/sh
set -eu
dockerd-entrypoint.sh --host=tcp://0.0.0.0:2375 &
daemon_pid=$!
trap 'kill "$daemon_pid"; wait "$daemon_pid"' TERM INT
attempt=0
until docker info >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then exit 1; fi
    sleep 1
done
if ! docker image inspect tervory-base-sandbox:python3.12 >/dev/null 2>&1; then
    docker import /opt/base-python.tar tervory-base-sandbox:python3.12 >/dev/null
fi
touch /tmp/base-sandbox-ready
wait "$daemon_pid"
