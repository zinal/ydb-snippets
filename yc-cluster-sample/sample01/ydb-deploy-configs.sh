#! /bin/sh

cp -v YdbWork/ydbd-config.yaml /opt/ydb/cfg/config.yaml
cp -v YdbWork/ydbd-storage.service /etc/systemd/system/
cp -v YdbWork/ydbd-testdb.service /etc/systemd/system/
systemctl daemon-reload
