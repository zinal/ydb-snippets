#! /bin/sh
# Создание пользователя и группы

create_ug() {
  vm_name="$1"
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo groupadd ydb >/dev/null 2>&1
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo useradd ydb -g ydb >/dev/null 2>&1
  ssh ${host_gw} ssh ${host_user}@${vm_name} sudo usermod -aG disk ydb >/dev/null 2>&1
  echo -n "${vm_name}: "
  ssh ${host_gw} ssh ${host_user}@${vm_name} id ydb
}

echo "Creating YDB user and group..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}-s${i}"
  create_ug ${vm_name}
done

# End Of File