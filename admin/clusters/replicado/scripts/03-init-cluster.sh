#! /bin/sh

./sw/ydb --ca-file certs/ca.crt \
    --client-cert-file certs/node.crt \
    --client-cert-key-file certs/node.key \
    -e grpcs://localhost:2135 \
    admin cluster bootstrap --uuid zztop1
echo $?
