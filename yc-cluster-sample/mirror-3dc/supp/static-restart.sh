#! /bin/sh
# Перезапуск статических нод YDB

echo "Re-starting YDB storage nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl stop ydbd-storage
  sleep 2
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo systemctl start ydbd-storage
  sleep 30
done

# End Of File