#! /bin/sh
# Запуск нод базы данных YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=`echo "${ydb_nodes} + ${ydb_nodes_extra}" | bc`

. ./supp/dynamic-start.sh

# End Of File