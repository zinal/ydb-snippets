#! /bin/sh
# Запуск статических нод

. ./options.sh

echo "Starting YDB database nodes..."
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl start ydbd-testdb
done
