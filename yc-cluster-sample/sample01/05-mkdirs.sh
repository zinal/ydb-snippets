#! /bin/sh
# Установка бинарника YDB на хосты кластера

. ./options.sh

build_dirs() {
  vm_name="$1"
  ssh ${host_gw} scp ${WORKDIR}/ydbd-unpack.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} screen -d -m ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydbd-unpack.sh
}

cat >ydbd-unpack.sh.tmp <<EOF
#! /bin/sh
echo -n "Unpacking ydbd at "
hostname -f
mkdir -p -v /opt/ydb/bin
mkdir -p -v /opt/ydb/cfg
xz -v -dc ${WORKDIR}/ydbd.xz >/opt/ydb/bin/ydbd
chmod aoug+x /opt/ydb/bin/ydbd
EOF

scp ydbd-unpack.sh.tmp ${host_gw}:${WORKDIR}/ydbd-unpack.sh

echo "Building installation directories..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  build_dirs ${vm_name}
done
echo "All jobs started!"
