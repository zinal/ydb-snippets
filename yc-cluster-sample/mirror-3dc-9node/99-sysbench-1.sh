#! /bin/sh
# Тест производительности.

. ./options.sh

scp sysbench.sh ${host_gw}:${WORKDIR}/

StartSysbench() {
  vm_name="$1"
  echo "...at host ${vm_name}..."
  ssh ${host_gw} ssh yc-user@${vm_name} mkdir -p ${WORKDIR}
  ssh ${host_gw} scp ${WORKDIR}/sysbench.sh yc-user@${vm_name}:${WORKDIR}/
  ssh ${host_gw} ssh yc-user@${vm_name} screen -d -m bash ${WORKDIR}/sysbench.sh
}

echo "Starting 2-hour sysbench sessions..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  StartSysbench ${vm_name}
done
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  StartSysbench ${vm_name}
done
