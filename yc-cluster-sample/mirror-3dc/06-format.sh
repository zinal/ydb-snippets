#! /bin/sh
# Форматирование дисков на кластере

. ./options.sh

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
  echo "sleep 2" >>$F
  echo "/opt/ydb/bin/ydbd admin bs disk obliterate /dev/disk/by-partlabel/${label}" >>$F
  echo 'ST=$?' >>$F
  echo 'echo "Status for '${disk}' -> '${label}' at "`hostname`": ${ST}"' >>$F
done

scp $F ${host_gw}:${WORKDIR}/ydb-disks-format.sh

echo "Partitioning disks..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} scp ${WORKDIR}/ydb-disks-format.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-disks-format.sh
done
