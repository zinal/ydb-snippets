#! /bin/sh
# Инициализация кластера хранения данных

. ./options.sh

scp ydb-initial-token.sh ${host_gw}:${WORKDIR}/
scp ydb-init-blobstorage.sh ${host_gw}:${WORKDIR}/
ssh ${host_gw} bash ${WORKDIR}/ydb-initial-token.sh "${host_base}-1"
ssh ${host_gw} scp ydbd-token-file yc-user@"${host_base}-1":ydbd-token-file
ssh ${host_gw} scp ${WORKDIR}/ydb-init-blobstorage.sh yc-user@"${host_base}-1":${WORKDIR}/
ssh ${host_gw} ssh yc-user@"${host_base}-1" bash ${WORKDIR}/ydb-init-blobstorage.sh
