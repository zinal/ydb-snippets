#! /bin/sh
# Остановка нод базы данных YDB

. ./options.sh

echo "Stopping YDB database nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl stop ydbd-testdb &
  sleep 1
done

wait

# End Of File