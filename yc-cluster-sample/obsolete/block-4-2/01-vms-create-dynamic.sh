#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

. ./options.sh

echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp

for i in `seq 9 16`; do
  vm_name="${host_base}-${i}"
  vm_disk_boot="${host_base}-${i}-boot"
  yc compute instance create ${vm_name} --zone ${yc_zone} \
    --platform ${yc_platform} \
    --ssh-key keyfile.tmp \
    --create-boot-disk name=${vm_disk_boot},type=network-ssd-nonreplicated,size=93G,auto-delete=true \
    --network-settings type=software-accelerated \
    --network-interface subnet-name=${yc_subnet},dns-record-spec="{name=${vm_name}.ru-central1.internal.}" \
    --memory 24G --cores 8 --async
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

echo "Validating network access..."
while true; do
  num_fail=0
  for i in `seq 9 16`; do
    vm_name="${host_base}-${i}"
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
for i in `seq 9 16`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo hostnamectl set-hostname ${vm_name}
  ssh ${host_gw} ssh yc-user@${vm_name} sudo timedatectl set-timezone Europe/Moscow
done
