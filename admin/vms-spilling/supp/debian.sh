#! /bin/sh
# Логика донастройки виртуальных машин Yandex Cloud для работы кластера YDB.

echo "apt-get update..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}${i}${yc_dns_suffix}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo apt-get update </dev/null >tmp-${vm_name}.txt 2>&1 &
done

wait

echo "apt-get install screen mc..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}${i}${yc_dns_suffix}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo apt-get install -y screen mc </dev/null >>tmp-${vm_name}.txt 2>&1 &
done

wait

echo "apt-get dist-upgrade..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}${i}${yc_dns_suffix}"
  ssh ${host_gw} ssh ${host_user}@${vm_name} screen -d -m sudo apt-get dist-upgrade -y </dev/null
done

# End Of File
