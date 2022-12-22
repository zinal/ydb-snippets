#! /bin/sh
# Запуск статических нод YDB

echo "Starting YDB storage nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl stop ydbd-storage
done

# End Of File