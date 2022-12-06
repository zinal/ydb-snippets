#! /bin/sh
# Распространение файлов настроек

. ./options.sh

scp ${ydb_config} ${host_gw}:${WORKDIR}/ydbd-config.yaml
scp ydbd-storage.service ydbd-testdb.service ydb-deploy-configs.sh \
  ${host_gw}:${WORKDIR}/

deploy_config() {
  vm_name="$1"
  conf_name="$2"
  ssh ${host_gw} scp ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} scp ${WORKDIR}/${conf_name} yc-user@${vm_name}:${WORKDIR}/ydbd-config.yaml
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh
}

echo "Deploying configuration files..."

for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  deploy_config ${vm_name} "ydbd-config.yaml"
done
