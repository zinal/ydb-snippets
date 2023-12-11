#! /bin/sh
# Обновление софта в виртуальных машинах.

. ./options.sh

set -u
set +e

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/debian.sh

# End Of File
