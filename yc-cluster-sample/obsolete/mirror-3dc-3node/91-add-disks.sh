#! /bin/sh
# Добавление дисков к виртуальным машинам статических нод.

. ./options.sh

echo "Creating disks..."
for i in `seq 1 3`; do
  vm_name="${host_base}-s${i}"
  for j in `seq 4 6`; do
    vm_disk_data="${host_base}-s${i}-data${j}"
    yc compute disk create ${vm_disk_data} --zone ${yc_zone} \
      --type network-ssd-nonreplicated --size 186G --async
  done
#  sleep 5
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

echo "Attaching disks to static node VMs..."
for i in `seq 1 3`; do
  vm_name="${host_base}-s${i}"
  for j in `seq 4 6`; do
    vm_disk="${host_base}-s${i}-data${j}"
    yc compute instance attach-disk ${vm_name} --disk-name ${vm_disk}
  done
done

echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp

