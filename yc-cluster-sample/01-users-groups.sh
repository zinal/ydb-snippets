#! /bin/sh
# Установка бинарника YDB на хосты кластера

. ./options.sh

echo "Creating YDB user and group..."
for i in `seq 1 8`; do
  vm_name="${host_base}-${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo groupadd ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo useradd ydb -g ydb >/dev/null 2>&1
  ssh ${host_gw} ssh yc-user@${vm_name} sudo usermod -aG disk ydb >/dev/null 2>&1
  echo -n "${vm_name}: "
  ssh ${host_gw} ssh yc-user@${vm_name} id ydb
done
