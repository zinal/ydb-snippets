#! /bin/sh
# Установка бинарника YDB на хосты кластера

host_gw=gw1
host_base=ycydb

SRCDIR=srcdir.tmp
WORKDIR=YdbWork

# ssh builder1.sas.yp-c.yandex.net ls -l ydbd.xz
# scp builder1.sas.yp-c.yandex.net:ydbd.xz srcdir.tmp/

ssh ${host_gw} mkdir ${WORKDIR}
scp ${SRCDIR}/ydbd.xz ${host_gw}:${WORKDIR}/

echo "Validating network access..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ZODAK_TEST=`ssh ${host_gw} ssh -o StrictHostKeyChecking=no yc-user@${vm_name} echo ZODAK`
  if [ "$ZODAK_TEST" == "ZODAK" ]; then
    echo "Host ${vm_name} is available."
  else
    echo "Host ${vm_name} IS NOT AVAILABLE!"
  fi
done
