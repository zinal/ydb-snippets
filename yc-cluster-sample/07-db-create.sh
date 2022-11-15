#! /bin/sh
# Создание базы данных

. ./options.sh

scp ydb-create-db.sh ${host_gw}:${WORKDIR}/
ssh ${host_gw} scp ${WORKDIR}/ydb-create-db.sh yc-user@"${host_base}-1":${WORKDIR}/
ssh ${host_gw} ssh yc-user@"${host_base}-1" bash ${WORKDIR}/ydb-create-db.sh
