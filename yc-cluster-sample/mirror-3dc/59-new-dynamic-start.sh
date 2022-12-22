#! /bin/sh
# Запуск вычислительных нод кластера YDB

. ./options.sh

set -u

ydb_nodes_begin=`echo "${ydb_nodes} + 1" | bc`
ydb_nodes_end=`echo "${ydb_nodes} + ${ydb_nodes_extra}" | bc`

. ./supp/dynamic-start.sh

# End Of File