#! /bin/bash

set -e
set -u

. ./options.sh

./start-storage.sh

./wait-storage.sh

cat data/databases | while read DBNAME; do
  if [[ ! -z "$DBNAME" ]]; then
    echo "** Starting database ${DBNAME}..."
    ./start-database.sh ${DBNAME}
  fi
done
