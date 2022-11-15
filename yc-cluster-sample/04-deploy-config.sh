#! /bin/sh
# Распространение файлов настроек

. ./options.sh

scp config-8nodes.yaml ydbd-storage.service ydbd-testdb.service ydb-deploy-configs.sh ${host_gw}:${WORKDIR}/

echo "Deploying configuration files..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} scp ${WORKDIR}/config-8nodes.yaml ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh
done
