#! /bin/sh
# Запуск статических нод

. ./options.sh

echo "Stopping YDB database nodes..."
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl stop ydbd-testdb
  ssh ${host_gw} ssh yc-user@${vm_name} sudo pkill -u ydb -s 9
done
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl stop ydbd-testdb
  ssh ${host_gw} ssh yc-user@${vm_name} sudo pkill -u ydb -s 9
  ssh ${host_gw} ssh yc-user@${vm_name} sudo shutdown -r now
done
