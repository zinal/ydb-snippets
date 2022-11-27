#! /bin/sh
# Запуск статических нод

. ./options.sh

echo "Stopping YDB database nodes..."
for i in `seq 1 4`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl stop ydbd-testdb
done
