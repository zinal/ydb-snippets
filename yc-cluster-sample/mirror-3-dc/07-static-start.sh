#! /bin/sh
# Запуск статических нод

. ./options.sh

echo "Starting YDB storage nodes..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl start ydbd-storage
done
