#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

. ./options.sh

echo "Retrieving public SSH keyfile ${keyfile_gw} from host ${host_gw}..."
ssh ${host_gw} cat ${keyfile_gw} >keyfile.tmp

for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  vm_disk_boot="${host_base}-d${i}-boot"
  yc compute instance create ${vm_name} --zone ${yc_zone} \
    --platform ${yc_platform} \
    --ssh-key keyfile.tmp \
    --create-boot-disk name=${vm_disk_boot},type=network-ssd-nonreplicated,size=93G,auto-delete=true \
    --network-settings type=software-accelerated \
    --network-interface subnet-name=${yc_subnet},dns-record-spec="{name=${vm_name}.ru-central1.internal.}" \
    --memory 24G --cores 12 --async
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
  for i in `seq 5 8`; do
    vm_name="${host_base}-d${i}"
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
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo hostnamectl set-hostname ${vm_name}
  ssh ${host_gw} ssh yc-user@${vm_name} sudo timedatectl set-timezone Europe/Moscow
done

echo "Creating YDB user and group..."
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo groupadd ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo useradd ydb -g ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo usermod -aG disk ydb >/dev/null 2>&1
  echo -n "${vm_name}: "
  ssh ${host_gw} ssh yc-user@${vm_name} id ydb
done

echo "Uploading ydbd compressed binary..."
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} mkdir ${WORKDIR}  >/dev/null 2>&1
  ssh ${host_gw} scp ${WORKDIR}/ydbd.xz yc-user@${vm_name}:${WORKDIR}/ydbd.xz
done

cat >ydbd-unpack.sh.tmp <<EOF
#! /bin/sh
echo -n "Unpacking ydbd at "
hostname -f
xz -v -dc ${WORKDIR}/ydbd.xz >/opt/ydb/bin/ydbd
EOF

scp ydbd-unpack.sh.tmp ${host_gw}:${WORKDIR}/ydbd-unpack.sh


echo "Building installation directories..."
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} scp ${WORKDIR}/ydbd-unpack.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo mkdir -p -v /opt/ydb/bin
  ssh ${host_gw} ssh yc-user@${vm_name} sudo mkdir -p -v /opt/ydb/cfg
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydbd-unpack.sh
  ssh ${host_gw} ssh yc-user@${vm_name} sudo chmod aoug+x /opt/ydb/bin/ydbd
done

scp config-3nodes.yaml ydbd-storage.service ydbd-testdb.service ydb-deploy-configs.sh ${host_gw}:${WORKDIR}/

echo "Deploying configuration files..."
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} scp ${WORKDIR}/config-3nodes.yaml ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh
done

echo "Starting YDB database nodes..."
for i in `seq 5 8`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo systemctl start ydbd-testdb
done
