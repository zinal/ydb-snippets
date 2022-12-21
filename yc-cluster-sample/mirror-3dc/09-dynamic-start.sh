#! /bin/sh
# Запуск нод базы данных YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/dynamic-start.sh

# End Of File