#! /bin/sh

LD_LIBRARY_PATH=/opt/ydb/lib
export LD_LIBRARY_PATH

if [ "tls"=="$1" ]; then

/opt/ydb/bin/ydbd -f ydbd-token-file --ca-file YdbWork/tls/ca.crt -s grpcs://`hostname -s`:2135 \
  admin blobstorage config init --yaml-file  /opt/ydb/cfg/config.yaml
echo "Blobstorage init status: $?"

else

/opt/ydb/bin/ydbd -f ydbd-token-file \
  admin blobstorage config init --yaml-file  /opt/ydb/cfg/config.yaml
echo "Blobstorage init status: $?"

fi
