#! /bin/sh
# Остановка всех видов нод

. ./options.sh

echo "Stopping YDB nodes..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl stop ydbd-testdb
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl stop ydbd-storage
done
