#! /bin/sh

rm -fv conf/*
./sw/ydb admin node config init --config-dir conf --from-config initial/ydb-initial-config.yaml
