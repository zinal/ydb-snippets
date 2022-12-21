#! /bin/sh
# Распространение файлов настроек YDB

scp conf/${ydb_config} ${host_gw}:${WORKDIR}/ydbd-config.yaml
scp ydb-deploy-configs.sh ${host_gw}:${WORKDIR}/

if [ "Y"=="$ydb_tls" ]; then
  TLSMODE=tls
  scp conf/ydbd-storage-tls.service ${host_gw}:${WORKDIR}/ydbd-storage.service
  scp conf/ydbd-testdb-tls.service  ${host_gw}:${WORKDIR}/ydbd-testdb.service
  ssh ${host_gw} mkdir -p ${WORKDIR}/tls
  (cd tls.tmp && scp -r * ${host_gw}:${WORKDIR}/tls/)
else
  TLSMODE=notls
  scp conf/ydbd-storage.service ${host_gw}:${WORKDIR}/
  scp conf/ydbd-testdb.service  ${host_gw}:${WORKDIR}/
fi

deploy_config() {
  vm_name="$1"
  conf_name="$2"
  echo "**** $vm_name"
  if [ "Y"=="$ydb_tls" ]; then
     ssh ${host_gw} ssh ${host_user}@${vm_name} mkdir -p ${WORKDIR}/tls
     ssh ${host_gw} scp ${WORKDIR}/tls/ca.crt ${host_user}@${vm_name}:${WORKDIR}/tls/ca.crt
     ssh ${host_gw} scp ${WORKDIR}/tls/${vm_name}/node.crt ${host_user}@${vm_name}:${WORKDIR}/tls/
     ssh ${host_gw} scp ${WORKDIR}/tls/${vm_name}/node.key ${host_user}@${vm_name}:${WORKDIR}/tls/
     ssh ${host_gw} scp ${WORKDIR}/tls/${vm_name}/web.pem ${host_user}@${vm_name}:${WORKDIR}/tls/
  fi
  ssh ${host_gw} scp ${WORKDIR}/ydbd-storage.service \
    ${WORKDIR}/ydbd-testdb.service ${WORKDIR}/ydb-deploy-configs.sh ${host_user}@${vm_name}:${WORKDIR}/
  ssh ${host_gw} scp ${WORKDIR}/${conf_name} ${host_user}@${vm_name}:${WORKDIR}/ydbd-config.yaml
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo bash ${WORKDIR}/ydb-deploy-configs.sh ${TLSMODE}
}

echo "Deploying configuration files..."

for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  deploy_config ${vm_name} "ydbd-config.yaml"
done

# End Of File