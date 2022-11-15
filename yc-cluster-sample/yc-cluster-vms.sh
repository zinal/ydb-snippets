#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

host_base=ycydb
yc_zone=ru-central1-b

echo "Creating disks..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  vm_disk_boot="${host_base}-${i}-boot"
  vm_disk_data1="${host_base}-${i}-data1"
  yc compute disk create ${vm_disk_boot} --zone ${yc_zone} \
    --type network-ssd-nonreplicated --size 93G --async
  yc compute disk create ${vm_disk_data1} --zone ${yc_zone} \
    --type network-ssd-nonreplicated --size 372G --async
done

echo "Waiting for disks to get ready..."
while true; do
  wcnt=`yc compute disk list --format json-rest | jq '.[].status' | grep -v READY | wc -l | (read x y && echo $x)`
  if [ "$wcnt" == "0" ]; then
    echo "...success!"
    break
  fi
  echo "...pending: ${wcnt}..."
  sleep 5
done
