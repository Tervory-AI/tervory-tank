#!/bin/sh
set -eu
export XDG_RUNTIME_DIR=/run/user/1000
mkdir -p "$XDG_RUNTIME_DIR"
rootlesskit --net=none --port-driver=builtin -p 0.0.0.0:2375:2375/tcp --copy-up=/etc --copy-up=/run \
    dockerd --rootless --host=unix:///run/user/1000/docker.sock --host=tcp://0.0.0.0:2375 \
    --tls=false --iptables=false --ip6tables=false --bridge=none --ip-forward=false --ip-masq=false &
daemon_pid=$!
trap 'kill "$daemon_pid"; wait "$daemon_pid"' TERM INT
attempt=0
until docker info >/dev/null 2>&1 && docker version >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then exit 1; fi
    sleep 1
done
if ! docker image inspect tervory-base-sandbox:python3.12 >/dev/null 2>&1; then
    docker import /opt/base-python.tar tervory-base-sandbox:python3.12 >/dev/null
fi
touch /tmp/base-sandbox-ready
wait "$daemon_pid"
