#! /bin/sh
# Загрузка бинарника YDB с промежуточного хоста на хосты кластера

. ./options.sh

upload_binary() {
  vm_name="$1"
  ssh ${host_gw} ssh yc-user@${vm_name} mkdir ${WORKDIR}  >/dev/null 2>&1
  ssh ${host_gw} screen -d -m scp ${WORKDIR}/ydbd.xz yc-user@${vm_name}:${WORKDIR}/ydbd.xz
}

echo "Uploading ydbd compressed binary to the nodes..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  upload_binary ${vm_name}
done
echo "All jobs started!"
