#! /bin/sh
# Установка дополнительных пакетов на узлы кластера.

. ./options.sh

echo "Installing extra APT packages..."
for i in `seq 1 ${ydb_static}`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get update
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get install -y screen
  ssh ${host_gw} ssh yc-user@${vm_name} screen -d -m sudo apt-get install -y bc mc atop zip unzip sysbench
done
for i in `seq 1 ${ydb_dynamic}`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get update
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get install -y screen
  ssh ${host_gw} ssh yc-user@${vm_name} screen -d -m sudo apt-get install -y bc mc atop zip unzip sysbench
done
