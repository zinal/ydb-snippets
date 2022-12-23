#! /bin/sh
# Ре-Инициализация кластера хранения данных YDB

if [ "Y"=="$ydb_tls" ]; then
  TLSMODE=tls
else
  TLSMODE=notls
fi

vm_name="${host_base}-s1"
scp ydb-initial-token.sh ydb-init-blobstorage.sh ${host_gw}:${WORKDIR}/

ssh ${host_gw} bash ${WORKDIR}/ydb-initial-token.sh ${vm_name} ${TLSMODE} ${ydb_root_password}
ssh ${host_gw} scp ydbd-token-file ${host_user}@"${vm_name}":ydbd-token-file

ssh ${host_gw} scp ${WORKDIR}/ydb-init-blobstorage.sh ${host_user}@"${vm_name}":${WORKDIR}/
ssh ${host_gw} ssh ${host_user}@"${vm_name}" bash -x ${WORKDIR}/ydb-init-blobstorage.sh ${TLSMODE}

# End Of File