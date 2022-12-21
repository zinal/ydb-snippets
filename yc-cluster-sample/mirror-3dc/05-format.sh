#! /bin/sh
# Форматирование дисков на кластере YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/format.sh

# End Of File