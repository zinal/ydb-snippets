#! /bin/sh

set -e
set -u

tls_mode=$1

cp -v YdbWork/ydbd-config.yaml /opt/ydb/cfg/config.yaml
cp -v YdbWork/ydbd-storage.service /etc/systemd/system/
cp -v YdbWork/ydbd-testdb.service /etc/systemd/system/
systemctl daemon-reload

if [ "tls"=="$tls_mode" ]; then
  mkdir -p /opt/ydb/certs
  cp -v YdbWork/tls/ca.crt /opt/ydb/certs/
  cp -v YdbWork/tls/node.crt /opt/ydb/certs/
  cp -v YdbWork/tls/node.key /opt/ydb/certs/
  cp -v YdbWork/tls/web.pem /opt/ydb/certs/
  chown -R ydb:ydb /opt/ydb/certs
  chmod 700 /opt/ydb/certs
fi
