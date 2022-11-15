#! /bin/sh
# Форматирование дисков на кластере

. ./options.sh

scp ydb-disk-format.sh ${host_gw}:${WORKDIR}/

echo "Partitioning disks..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} scp ${WORKDIR}/ydb-disk-format.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-disk-format.sh
done
