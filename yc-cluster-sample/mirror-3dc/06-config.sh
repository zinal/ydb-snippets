#! /bin/sh
# Распространение файлов настроек YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/config.sh

# End Of File