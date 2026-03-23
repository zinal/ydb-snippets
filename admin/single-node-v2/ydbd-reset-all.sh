#! /bin/bash

PATH=/opt/kikimr/bin:$PATH
export PATH

YDBD_CONFIG=/opt/kikimr/conf/config-storage.yaml
export YDBD_CONFIG

set -u
set +e

echo "** Shutting down..."
systemctl stop ydbd-pgdata
systemctl stop ydbd-storage

set -e

echo "** Disk cleanup..."
dd if=/dev/zero of=/dev/disk/by-partlabel/ydb_data_1 bs=1M count=1

echo "** Starting up storage..."
systemctl start ydbd-storage
sleep 5

echo "** Initializing storage..."
ydbd admin bs config init --yaml-file $YDBD_CONFIG

echo "** Setting database limits..."
rm -f /tmp/ydb_admin_limits_command.txt
cat <<EOF > /tmp/ydb_admin_limits_command.txt
(
  (let key '('('PathId (Uint64 '1))))
  (let paths '('PathsLimit (Uint64 '50000000)))
  (let backups '('ConsistentCopyingTargetsLimit (Uint64 '50000000)))
  (let tableColumns '('TableColumnsLimit (Uint64 '100000)))
  (let tableIndices '('TableIndicesLimit (Uint64 '50000)))
  (let ret (AsList (UpdateRow 'SubDomains key '(paths backups tableColumns tableIndices))))
  (return ret)
)
EOF
SCHEME_TABLET_ID="$(yq '.system_tablets.flat_schemeshard[0].info.tablet_id' $YDBD_CONFIG)"
ydbd -s localhost:2135 admin tablet $SCHEME_TABLET_ID execute /tmp/ydb_admin_limits_command.txt
rm -f /tmp/ydb_admin_limits_command.txt

echo "Creating database..."
ydbd admin database "/local/pg-data" create ssd:5

echo "Starting database..."
systemctl start ydbd-pgdata
