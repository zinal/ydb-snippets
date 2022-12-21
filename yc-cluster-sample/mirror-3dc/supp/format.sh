#! /bin/sh
# Форматирование дисков на кластере YDB

F=partme.sh.tmp
echo "#!/bin/sh" >$F

echo "LD_LIBRARY_PATH=/opt/ydb/lib" >>$F
echo "export LD_LIBRARY_PATH" >>$F

n=0
for x in b c d e f g h i; do
  n=`echo "$n + 1" | bc`
  if [ $n -gt $ydb_disk_count ]; then
    break
  fi
  disk=/dev/vd${x}
  label=ydb_disk_${n}
  echo "parted ${disk} mklabel gpt -s" >>$F
  echo "parted -a optimal ${disk} mkpart primary '0%' '100%'" >>$F
  echo "parted ${disk} name 1 ${label}" >>$F
  echo "partprobe ${disk}" >>$F
  echo "sleep 1" >>$F
  echo "/opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/${label}" >>$F
  echo 'ST=$?' >>$F
  echo 'echo "Status for '${disk}' -> '${label}' at "`hostname`": ${ST}"' >>$F
done

scp $F ${host_gw}:${WORKDIR}/ydb-disks-format.sh

echo "Partitioning disks..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} scp ${WORKDIR}/ydb-disks-format.sh ${host_user}@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo bash ${WORKDIR}/ydb-disks-format.sh
done

# End Of File