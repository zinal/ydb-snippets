#! /bin/sh

set -e
set -u

tls_mode=$1

cp -v YdbWork/ydbd-config.yaml /opt/ydb/cfg/config.yaml
cp -v YdbWork/ydbd-storage.service /etc/systemd/system/
cp -v YdbWork/ydbd-testdb.service /etc/systemd/system/
systemctl daemon-reload

if [ "tls"=="$tls_mode" ]; then
  mkdir -p /opt/ydb/cert
  cp -v YdbWork/tls/ca.crt /opt/ydb/cert/
  cp -v YdbWork/tls/node.crt /opt/ydb/cert/
  cp -v YdbWork/tls/node.key /opt/ydb/cert/
  chown -R ydb:ydb /opt/ydb/cert
  chmod 700 /opt/ydb/cert
fi
