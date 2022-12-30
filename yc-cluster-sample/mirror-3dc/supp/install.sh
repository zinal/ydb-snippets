#! /bin/sh
# Создание каталогов инсталляции и распаковка дистрибутива YDB

build_dirs() {
  vm_name="$1"
  ssh ${host_gw} scp ${WORKDIR}/ydbd-unpack.sh ${host_user}@${vm_name}:${WORKDIR}/
  ssh ${host_gw} screen -d -m ssh ${host_user}@${vm_name} sudo bash ${WORKDIR}/ydbd-unpack.sh
}

cat >ydbd-unpack.sh.tmp <<EOF
#! /bin/sh
echo -n "Unpacking ydbd at "
hostname -f
mkdir -p -v /opt/ydb/bin
mkdir -p -v /opt/ydb/cfg
mkdir -p -v /opt/ydb/audit
chmod 700 /opt/ydb/audit
chown ydb:ydb /opt/ydb/audit
if [ -f ${WORKDIR}/ydbd.xz ]; then
xz -v -dc ${WORKDIR}/ydbd.xz >/opt/ydb/bin/ydbd
chmod aoug+x /opt/ydb/bin/ydbd
else
tar -x -f ${WORKDIR}/ydbd.tar.gz --strip-component=1 -C /opt/ydb
fi
EOF

scp ydbd-unpack.sh.tmp ${host_gw}:${WORKDIR}/ydbd-unpack.sh

echo "Building installation directories..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  build_dirs ${vm_name}
done
echo "All jobs started!"

# End Of File