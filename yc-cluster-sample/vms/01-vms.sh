#! /bin/sh
# Создание виртуальных машин Yandex Cloud для работы кластера YDB.

. ./options.sh

set -u
set +e

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/vms.sh

# End Of File
