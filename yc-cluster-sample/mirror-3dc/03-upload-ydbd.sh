#! /bin/sh
# Создание пользователя и группы

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/upload-ydbd.sh

# End Of File