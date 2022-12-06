#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

. ./options.sh

checkLimit() {
  grep "The limit on maximum number of active operations has exceeded" mkinst.tmp | wc -l | (read x && echo $x)
}

echo "Creating disks..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  for j in `seq 1 ${ydb_disk_count}`; do
    vm_disk_data="${host_base}-s${i}-data${j}"
    echo "...${vm_disk_data}"
    while true; do
      yc compute disk create ${vm_disk_data} --zone ${yc_zone} \
        --type network-ssd-nonreplicated --size 372G --async >mkinst.tmp 2>&1
      cnt=`checkLimit`
      if [ "$cnt" == "0" ]; then break; else sleep 10; fi
    done
  done
done
cnt=`grep "ERROR:" mkinst.tmp | wc -l`
if [ $cnt -gt 0 ]; then
    echo "*** ERROR: disk creation failed, ABORTING!"
    cat mkinst.tmp
    exit 1
fi

echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp
ssh ${host_gw} rm -f .ssh/known_hosts

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

echo "Creating static node VMs..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  vm_disk_boot="${host_base}-s${i}-boot"

  disk_datum=""
  for j in `seq 1 ${ydb_disk_count}`; do
    disk_datum="$disk_datum --attach-disk disk-name=${host_base}-s${i}-data${j},auto-delete=true"
  done
  echo "...${vm_name}"
  while true; do
    yc compute instance create ${vm_name} --zone ${yc_zone} \
      --platform ${yc_platform} \
      --ssh-key keyfile.tmp \
      --create-boot-disk ${yc_vm_image},name=${vm_disk_boot},type=network-ssd-nonreplicated,size=93G,auto-delete=true \
      ${disk_datum} --network-settings type=software-accelerated \
      --network-interface subnet-name=${yc_subnet},dns-record-spec="{name=${vm_name}.ru-central1.internal.}" \
      --memory 64G --cores 32 --async >mkinst.tmp 2>&1
    cnt=`checkLimit`
    if [ "$cnt" == "0" ]; then break; else sleep 10; fi
  done
done
cnt=`grep "ERROR:" mkinst.tmp | wc -l`
if [ $cnt -gt 0 ]; then
    echo "*** ERROR: VM creation failed, ABORTING!"
    cat mkinst.tmp
    exit 1
fi

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

echo "Validating network access..."
while true; do
  num_fail=0
  t=s
  for i in `seq 1 ${ydb_static}`; do
    vm_name="${host_base}-s${i}"
    ZODAK_TEST=`ssh ${host_gw} ssh -o StrictHostKeyChecking=no yc-user@${vm_name} echo ZODAK 2>/dev/null`
    if [ "$ZODAK_TEST" == "ZODAK" ]; then
      echo "Host ${vm_name} is available."
    else
      echo "Host ${vm_name} IS NOT AVAILABLE!"
      num_fail=`echo "$num_fail + 1" | bc`
    fi
  done
  if [ $num_fail -gt 0 ]; then
    echo "*** Cannot move forward, $num_fail hosts unavailable!"
  else
    echo "*** VMs are ready, moving forward..."
    break
  fi
done

echo "Configuring host names and timezones..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo hostnamectl set-hostname ${vm_name}
  ssh ${host_gw} ssh yc-user@${vm_name} sudo timedatectl set-timezone Europe/Moscow
done

# End Of File
