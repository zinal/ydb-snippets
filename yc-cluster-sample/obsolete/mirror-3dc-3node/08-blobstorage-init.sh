#! /bin/sh
# Инициализация кластера хранения данных

. ./options.sh

vm_name="${host_base}-s1"
scp ydb-initial-token.sh ${host_gw}:${WORKDIR}/
scp ydb-init-blobstorage.sh ${host_gw}:${WORKDIR}/
ssh ${host_gw} bash ${WORKDIR}/ydb-initial-token.sh ${vm_name}
ssh ${host_gw} scp ydbd-token-file yc-user@"${vm_name}":ydbd-token-file
ssh ${host_gw} scp ${WORKDIR}/ydb-init-blobstorage.sh yc-user@"${vm_name}":${WORKDIR}/
ssh ${host_gw} ssh yc-user@"${vm_name}" bash ${WORKDIR}/ydb-init-blobstorage.sh
