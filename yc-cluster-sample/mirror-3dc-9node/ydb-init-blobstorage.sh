#! /bin/sh

/opt/ydb/bin/ydbd -f ydbd-token-file admin blobstorage config init --yaml-file  /opt/ydb/cfg/config.yaml
echo "Blobstorage init status: $?"
