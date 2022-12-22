#! /bin/sh
# Запуск статических нод YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/static-restart.sh

# End Of File