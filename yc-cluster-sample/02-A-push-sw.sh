#! /bin/sh
# Установка бинарника YDB на хосты кластера

. ./options.sh

# ssh builder1.sas.yp-c.yandex.net ls -l ydbd.xz
# scp builder1.sas.yp-c.yandex.net:ydbd.xz srcdir.tmp/

ssh ${host_gw} mkdir -p ${WORKDIR}
scp ${SRCDIR}/ydbd.xz ${host_gw}:${WORKDIR}/

echo "Uploading ydbd compressed binary..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
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
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} scp ${WORKDIR}/ydbd-unpack.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo mkdir -p -v /opt/ydb/bin
  ssh ${host_gw} ssh yc-user@${vm_name} sudo mkdir -p -v /opt/ydb/cfg
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydbd-unpack.sh
  ssh ${host_gw} ssh yc-user@${vm_name} sudo chmod aoug+x /opt/ydb/bin/ydbd
done
