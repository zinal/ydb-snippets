#! /bin/sh
# Логика донастройки виртуальных машин Yandex Cloud для работы кластера YDB.

echo "Configuring host names and timezones..."
for i in `seq ${ydb_nodes_begin} ${ydb_nodes_end}`; do
  vm_name="${host_base}${i}${yc_dns_suffix}"
  assign_hostname=${vm_name}
  if [ ! -z "${yc_dns_suffix_back}" ]; then
    if [ ! -z "${host_base_back}" ]; then
      assign_hostname="${host_base_back}${i}${yc_dns_suffix_back}"
    else
      assign_hostname="${host_base}${i}${yc_dns_suffix_back}"
    fi
  fi
  echo "  -> ${vm_name}"
  ssh ${host_gw} ssh -o StrictHostKeyChecking=no ${host_user}@${vm_name} sudo hostnamectl set-hostname ${assign_hostname}
  ssh ${host_gw} ssh -o StrictHostKeyChecking=no ${host_user}@${vm_name} sudo timedatectl set-timezone Europe/Moscow
  if [ "Y" == "$ydb_restart_hosts" ]; then
    ssh ${host_gw} ssh -o StrictHostKeyChecking=no ${host_user}@${vm_name} sudo shutdown -r now
  fi
done

wait

echo "...done!"

# End Of File
