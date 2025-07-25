#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

. ./options.sh

set +e
set +u

if [ -z "$ydb_nodes_begin" ]; then
  ydb_nodes_begin=1
fi
set -u
ydb_nodes_end=${ydb_nodes}

. ./supp/host.sh

# End Of File
