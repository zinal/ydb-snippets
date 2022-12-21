#! /bin/sh
# Загрузка бинарника YDB на промежуточный хост

. ./options.sh

# ssh builder1.sas.yp-c.yandex.net ls -l ydbd.xz
# scp builder1.sas.yp-c.yandex.net:ydbd.xz srcdir.tmp/

echo "Uploading ydbd compressed binary to the gateway..."
ssh ${host_gw} mkdir -p ${WORKDIR}
scp ${SRCDIR}/ydbd.tar.gz ${host_gw}:${WORKDIR}/
