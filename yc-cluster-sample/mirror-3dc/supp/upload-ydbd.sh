#! /bin/sh
# Загрузка бинарника YDB с промежуточного хоста на хосты кластера

upload_binary() {
  vm_name="$1"
  ssh ${host_gw} ssh ${host_user}@${vm_name} mkdir ${WORKDIR}  >/dev/null 2>&1
  ssh ${host_gw} screen -d -m scp ${WORKDIR}/${YDBD_ARCHIVE} ${host_user}@${vm_name}:${WORKDIR}/
}

echo "Uploading ydbd compressed binary to the nodes..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  echo "...${vm_name}"
  upload_binary ${vm_name}
done
echo "All jobs started!"

# End Of File