#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

host_gw=gw1
keyfile_gw=.ssh/id_ecdsa.pub
host_base=ycydb
yc_zone=ru-central1-b

echo "Creating disks..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  vm_disk_data1="${host_base}-${i}-data1"
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

echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp

for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  vm_disk_boot="${host_base}-${i}-boot"
  vm_disk_data1="${host_base}-${i}-data1"
  yc compute instance create ${vm_name} --zone ${yc_zone} \
    --ssh-key keyfile.tmp \
    --create-boot-disk name=${vm_disk_boot},type=network-ssd-nonreplicated,size=93G,auto-delete=true \
    --attach-disk disk-name=${vm_disk_data1},auto-delete=true \
    --network-settings type=software-accelerated \
    --memory 32G --cores 8 --async
done

echo "Waiting for VMs to get ready..."
while true; do
  wcnt=`yc compute instances list --format json-rest | jq '.[].status' | grep -vE '(RUNNING|STOPPED)' | wc -l | (read x y && echo $x)`
  if [ "$wcnt" == "0" ]; then
    echo "...success!"
    break
  fi
  echo "...pending: ${wcnt}..."
  sleep 5
done

