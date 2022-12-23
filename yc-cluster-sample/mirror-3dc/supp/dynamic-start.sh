#! /bin/sh
# Запуск вычислительных нод YDB

echo "Starting YDB database nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl start ydbd-testdb &
  sleep 1
done

echo "Jobs started, waiting..."
wait

# End Of File