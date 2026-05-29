#!/usr/bin/env bash
# ============================================================================
# Развёртывание кластера YDB на 6 ВМ:
#   - 3 ВМ для узлов хранения (group ydbd_static)
#   - 3 ВМ для узлов базы данных db1 (group ydbd_dynamic)
#
# Стандартный playbook ydb_platform.ydb.initial_setup НЕ ПОДХОДИТ для такой
# топологии, потому что он применяет роль ydbd_static ко всем хостам группы
# `ydb`, включая узлы БД. Вместо него вызываем granular playbook'и в нужном
# порядке.
#
# Перед запуском убедитесь, что:
#   - inventory/50-inventory.yaml содержит реальные FQDN ВМ и SSH-параметры;
#   - inventory/99-inventory-vault.yaml содержит пароль и зашифрован
#     командой:  ansible-vault encrypt inventory/99-inventory-vault.yaml
#   - ansible_vault_password_file содержит пароль для расшифровки vault'а;
#   - архив YDB лежит по пути ydb_archive (см. инвентарь, по умолчанию
#     /opt/ydb-dist/ydbd-server.tar.gz) на ЭТОМ управляющем хосте
#     (доставку на 6 ВМ обеспечит сам Ansible);
#   - установлены коллекции:
#       ansible-galaxy collection install git+https://github.com/ydb-platform/ydb-ansible.git,latest
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")"

echo "==> [1/5] prepare_host: подготовка всех 6 ВМ (пакеты, chrony, sysctl, ydb-user и т.д.)"
ansible-playbook ydb_platform.ydb.prepare_host

echo "==> [2/5] binaries_all: доставка ydb_archive с управляющего хоста и распаковка в /opt/ydb на всех 6 ВМ"
ansible-playbook ydb_platform.ydb.binaries_all

echo "==> [3/5] install_static: bootstrap кластера хранения и применение dynconfig"
echo "         ВНИМАНИЕ: ограничиваем хосты группой ydbd_static, иначе роль"
echo "         попытается запустить ydbd-storage и на узлах БД."
ansible-playbook ydb_platform.ydb.install_static -l ydbd_static

echo "==> [4/5] create_database: создание базы /rnd-ydb/db1 с 3 группами хранения"
echo "         Этот playbook автоматически использует группу ydbd_static."
ansible-playbook ydb_platform.ydb.create_database

echo "==> [5/5] install_dynamic: запуск динамических узлов на 3 ВМ группы ydbd_dynamic"
echo "         Этот playbook автоматически использует группу ydbd_dynamic."
ansible-playbook ydb_platform.ydb.install_dynamic

cat <<'EOF'

============================================================================
Развёртывание завершено.

  Domain:    /rnd-ydb
  Database:  /rnd-ydb/db1
  Storage:   mirror-3-dc (3-node), 3 storage groups, kind=ssd
  Brokers:   storage-a/b/c.rnd-ydb.example.com :2135  (grpcs)
  Dynnodes:  database-a/b/c.rnd-ydb.example.com :2136 (grpcs)
  Monitoring (Embedded UI):
    Static:    https://storage-a.rnd-ydb.example.com:8765
    Dynamic:   https://database-a.rnd-ydb.example.com:8766

Проверка соединения с базой:
  ydb -e grpcs://storage-a.rnd-ydb.example.com:2135 \
      -d /rnd-ydb/db1 \
      --ca-file files/TLS/certs/ca.crt \
      --user root \
      sql -s 'SELECT 1;'

Обновление настроек памяти БД (повторное применение dynconfig):
  ansible-playbook ydb_platform.ydb.update_dynconfig
============================================================================
EOF
