#! /bin/sh
# Тест производительности.

. ./options.sh

mkdir -p sysbench.out.tmp

GrabSysbench() {
  vm_name="$1"
  fname=sysbench.${vm_name}.8c.txt
  echo "...from host ${vm_name}..."
  ssh ${host_gw} scp yc-user@${vm_name}:sysbench.out.txt ${WORKDIR}/${fname}
  scp ${host_gw}:${WORKDIR}/${fname} sysbench.out.tmp/
}

echo "Collecting sysbench output..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  GrabSysbench ${vm_name}
done
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  GrabSysbench ${vm_name}
done
