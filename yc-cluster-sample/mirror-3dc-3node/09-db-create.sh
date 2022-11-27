#! /bin/sh
# Создание базы данных

. ./options.sh

vm_name="${host_base}-s1"
scp ydb-create-db.sh ${host_gw}:${WORKDIR}/
ssh ${host_gw} scp ${WORKDIR}/ydb-create-db.sh yc-user@"${vm_name}":${WORKDIR}/
ssh ${host_gw} ssh yc-user@"${vm_name}" bash ${WORKDIR}/ydb-create-db.sh
