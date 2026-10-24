#! /bin/sh

./sw/ydb -e grpcs://localhost:2135 -d /Root --ca-file certs/ca.crt \
  --user root --no-password auth get-token --force > auth_token
