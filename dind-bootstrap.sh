#!/usr/bin/env sh
set -eu

NET="${COMPOSE_PROJECT_NAME:-binancetradingbot}_sandboxnet"

# 1) discover bridge on the host daemon
BRIDGE=$(docker --host=unix:///docker-host.sock \
         network inspect -f '{{ index .Options "com.docker.network.bridge.name" }}' "$NET" 2>/dev/null || true)

if [ -z "$BRIDGE" ]; then
  BRIDGE=$(docker --host=unix:///docker-host.sock \
           network inspect -f '{{ .Id }}' "$NET" | cut -c1-12 | xargs printf 'br-%s')
fi

# 2) launch inner dockerd on its own sock + TCP
dockerd-entrypoint.sh \
  --bridge="$BRIDGE" \
  -H unix:///var/run/docker.sock \
  -H tcp://0.0.0.0:2375 &
while ! docker info >/dev/null 2>&1; do sleep 0.3; done

# 3) register network name inside DinD
docker network create \
  --driver bridge \
  --opt "com.docker.network.bridge.name=$BRIDGE" \
  --subnet 172.19.0.0/16 \
  "$NET" 2>/dev/null || true

tail -f /dev/null
