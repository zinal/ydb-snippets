#! /bin/sh
# Создание каталогов инсталляции и распаковка дистрибутива YDB

. ./options.sh

set -u

ydb_nodes_begin=1
ydb_nodes_end=${ydb_nodes}

. ./supp/install.sh

# End Of File