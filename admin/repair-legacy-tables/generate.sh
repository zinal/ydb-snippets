#!/usr/bin/env bash
# Regenerate Go stubs from minimal private protos.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$(go env GOPATH)/bin:${PATH}"

protoc -I "$ROOT/protos" \
  --go_out="$ROOT/pkg/kikimr" \
  --go_opt=module=github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr \
  --go-grpc_out="$ROOT/pkg/kikimr" \
  --go-grpc_opt=module=github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr \
  "$ROOT/protos/scheme_op.proto" \
  "$ROOT/protos/tx_proxy.proto" \
  "$ROOT/protos/msgbus.proto" \
  "$ROOT/protos/grpc.proto"

echo "Generated stubs under $ROOT/pkg/kikimr"
