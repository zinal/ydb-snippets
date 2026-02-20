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
      --grpcs-port=${YDB_PORT_APP} --mon-port=${YDB_PORT_UI} --ic-port=${YDB_PORT_IC} \
      </dev/null >>logs/server.log 2>&1 &
echo "$!" >logs/server.pid
