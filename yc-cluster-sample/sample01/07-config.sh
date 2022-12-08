#! /bin/sh
# Распространение файлов настроек

. ./options.sh

scp ${ydb_config} ${host_gw}:${WORKDIR}/ydbd-config.yaml
scp ydbd-storage.service ydbd-testdb.service ydb-deploy-configs.sh \
  ${host_gw}:${WORKDIR}/

if [ "Y"=="$ydb_tls" ]; then
  TLSMODE=tls
  ssh ${host_gw} mkdir -p ${WORKDIR}/tls
  (cd tls.tmp && scp *.crt *.key ${host_gw}:${WORKDIR}/tls/)
else
  TLSMODE=notls
fi

deploy_config() {
  vm_name="$1"
  conf_name="$2"
  if [ "Y"=="$ydb_tls" ]; then
     ssh ${host_gw} ssh yc-user@${vm_name} mkdir -p ${WORKDIR}/tls
     ssh ${host_gw} scp ${WORKDIR}/tls/ca.crt yc-user@${vm_name}:${WORKDIR}/tls/ca.crt
     ssh ${host_gw} scp ${WORKDIR}/tls/${vm_name}.crt yc-user@${vm_name}:${WORKDIR}/tls/node.crt
     ssh ${host_gw} scp ${WORKDIR}/tls/${vm_name}.key yc-user@${vm_name}:${WORKDIR}/tls/node.key
  fi
  ssh ${host_gw} scp ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} scp ${WORKDIR}/${conf_name} yc-user@${vm_name}:${WORKDIR}/ydbd-config.yaml
  ssh ${host_gw} ssh yc-user@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh ${TLSMODE}
}

echo "Deploying configuration files..."

for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  deploy_config ${vm_name} "ydbd-config.yaml"
done
