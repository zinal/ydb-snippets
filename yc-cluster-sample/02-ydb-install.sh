#! /bin/sh
# Установка бинарника YDB на хосты кластера

host_gw=gw1
host_base=ycydb

SRCDIR=srcdir.tmp
WORKDIR=YdbWork

echo "Validating network access..."
num_fail=0
for i in `seq 1 8`; do
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
  echo "Cannot move forward, $num_fail hosts unavailable!"
  exit 1
fi

echo "Creating YDB user and group..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo groupadd ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo useradd ydb -g ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo usermod -aG disk ydb >/dev/null 2>&1
  echo -n "${vm_name}: "
  ssh ${host_gw} ssh yc-user@${vm_name} id ydb
done

echo "Uploading ydbd compressed binary..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} mkdir ${WORKDIR}  >/dev/null 2>&1
  ssh ${host_gw} scp ${WORKDIR}/ydbd.xz yc-user@${vm_name}:${WORKDIR}/ydbd.xz
done
