#! /bin/sh
# Удаление виртуальных машин Yandex Cloud.

. ./options.sh

set -u
set +u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

echo ${ydb_nodes_begin}" -> "${ydb_nodes_end}
. ./supp/drop-all.sh

ydb_nodes_begin=`echo "${ydb_nodes} + 1" | bc`
ydb_nodes_end=`echo "${ydb_nodes} + ${ydb_nodes_extra}" | bc`

echo ${ydb_nodes_begin}" -> "${ydb_nodes_end}
. ./supp/drop-all.sh

# End Of File
