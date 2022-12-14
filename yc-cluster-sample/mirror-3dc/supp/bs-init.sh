#! /bin/sh
# Инициализация кластера хранения данных YDB

if [ "Y"=="$ydb_tls" ]; then
  TLSMODE=tls
else
  TLSMODE=notls
fi

vm_name="${host_base}-s1"
scp ydb-initial-token.sh ydb-init-blobstorage.sh ydb-create-db.sh ${host_gw}:${WORKDIR}/

ssh ${host_gw} bash ${WORKDIR}/ydb-initial-token.sh ${vm_name} ${TLSMODE}
ssh ${host_gw} scp ydbd-token-file ${host_user}@"${vm_name}":ydbd-token-file

ssh ${host_gw} scp ${WORKDIR}/ydb-init-blobstorage.sh ${host_user}@"${vm_name}":${WORKDIR}/
ssh ${host_gw} ssh ${host_user}@"${vm_name}" bash ${WORKDIR}/ydb-init-blobstorage.sh ${TLSMODE}

ssh ${host_gw} scp ${WORKDIR}/ydb-create-db.sh ${host_user}@"${vm_name}":${WORKDIR}/
ssh ${host_gw} ssh ${host_user}@"${vm_name}" bash ${WORKDIR}/ydb-create-db.sh ${ydb_disk_groups} ${TLSMODE}

# End Of File