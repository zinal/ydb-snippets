#! /bin/sh
# Форматирование дисков на кластере YDB

. ./options.sh

set -u

ydb_nodes_begin=`echo "${ydb_nodes} + 1" | bc`
ydb_nodes_end=`echo "${ydb_nodes} + ${ydb_nodes_extra}" | bc`

. ./supp/format.sh

# End Of File