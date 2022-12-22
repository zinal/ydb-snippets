#! /bin/sh
# Создание пользователя и группы

. ./options.sh

set -u

ydb_nodes_begin=`echo "${ydb_nodes} + 1" | bc`
ydb_nodes_end=`echo "${ydb_nodes} + ${ydb_nodes_extra}" | bc`

. ./supp/ug.sh

# End Of File