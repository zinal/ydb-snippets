#! /bin/sh
# Логика создания виртуальных машин Yandex Cloud для работы кластера YDB.

if [ "1" == "$ydb_nodes_begin" ]; then
  set -e
  echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
  ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp
  ssh ${host_gw} rm -f .ssh/known_hosts
  set +e
fi

checkLimit() {
  grep "The limit on maximum number of active operations has exceeded" mkinst.tmp | wc -l | (read x && echo $x)
}

echo "Creating dynamic node VMs..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}${i}"
  vm_disk_boot="${host_base}${i}-boot"
  echo "...${vm_name}"
  while true; do
    yc compute instance create ${vm_name} --zone ${yc_zone} \
      --platform ${yc_platform} \
      --ssh-key keyfile.tmp \
      --create-boot-disk ${yc_vm_image},name=${vm_disk_boot},type=network-ssd-nonreplicated,size=93G,auto-delete=true \
      --network-settings type=software-accelerated \
      --network-interface subnet-name=${yc_subnet},dns-record-spec="{name=${vm_name}.ru-central1.internal.}" \
      --memory ${yc_vm_mem} --cores ${yc_vm_cores} --async >mkinst.tmp 2>&1
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

ssh ${host_gw} resolvectl flush-caches

echo "Validating network access..."
while true; do
  num_fail=0
  t=s
  for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
    vm_name="${host_base}${i}"
    ZODAK_TEST=`ssh ${host_gw} ssh -o StrictHostKeyChecking=no ${host_user}@${vm_name} echo ZODAK 2>/dev/null`
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

# End Of File
