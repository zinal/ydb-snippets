#! /bin/sh
# Распространение файлов настроек

. ./options.sh

scp config-3nodes.yaml ydbd-storage.service ydbd-testdb.service ydb-deploy-configs.sh ${host_gw}:${WORKDIR}/

deploy_config() {
  vm_name="$1"
  ssh ${host_gw} scp ${WORKDIR}/config-3nodes.yaml ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh
}

echo "Deploying configuration files..."
for i in `seq 1 3`; do
  vm_name="${host_base}-s${i}"
  deploy_config ${vm_name}
done
for i in `seq 1 4`; do
  vm_name="${host_base}-d${i}"
  deploy_config ${vm_name}
done
