#! /bin/sh
# Создание пользователя и группы

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/ug.sh

# End Of File