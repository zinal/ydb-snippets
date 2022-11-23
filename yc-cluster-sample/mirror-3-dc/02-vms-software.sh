#! /bin/sh
# Установка дополнительных пакетов на узлы кластера.

. ./options.sh

echo "Installing extra APT packages..."
for i in `seq 1 3`; do
  vm_name="${host_base}-s${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get update
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get install -y bc screen mc atop zip unzip
done
for i in `seq 1 4`; do
  vm_name="${host_base}-d${i}"
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get update
  ssh ${host_gw} ssh yc-user@${vm_name} sudo apt-get install -y bc screen mc atop zip unzip
done
