#! /bin/sh
# Установка бинарника YDB на хосты кластера

. ./options.sh

create_ug() {
  vm_name="$1"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo groupadd ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo useradd ydb -g ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo usermod -aG disk ydb >/dev/null 2>&1
  echo -n "${vm_name}: "
  ssh ${host_gw} ssh yc-user@${vm_name} id ydb
}

echo "Creating YDB user and group..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  create_ug ${vm_name}
done
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  create_ug ${vm_name}
done
