#! /bin/sh
# Полный цикл операций по запуску кластера YDB.
# Ненадёжная конструкция, поскольку полагается на задержки между асинхронными операциями.

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

set +e
. ./supp/vms.sh
set -e
. ./supp/upload-ydbd.sh
. ./supp/ug.sh

sleep 5

. ./supp/install.sh

sleep 20

. ./supp/format.sh
. ./supp/config.sh
. ./supp/static-start.sh

sleep 60

. ./supp/bs-init.sh

sleep 20

. ./supp/dynamic-start.sh

# End Of File
