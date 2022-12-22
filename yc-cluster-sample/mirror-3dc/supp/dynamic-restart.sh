#! /bin/sh
# Перезапуск динамических нод YDB

echo "Re-starting YDB database nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl stop ydbd-testdb
  sleep 2
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl start ydbd-testdb
  sleep 30
done

# End Of File