#! /usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

date >>logs/server.log
echo "****************************************" >>logs/server.log
echo "Starting ydbd server, user: `whoami`" >>logs/server.log
echo "****************************************" >>logs/server.log

nohup ./app/ydbd server --yaml-config=config/config.yaml --node=1 \
      --grpc-ca certs/ca.crt --mon-cert certs/web.pem --ca=certs/ca.crt \
      --grpcs-port=2135 --mon-port=8765 --ic-port=19001 \
      </dev/null >>logs/server.log 2>&1 &
echo "$!" >logs/server.pid
