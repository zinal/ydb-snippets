#! /bin/bash

set -e
set -u

. ./options.sh

SVC_STATIC=`cat data/svc-static`

cat data/databases | while read DBNAME; do
  if [[ ! -z "$DBNAME" ]]; then
    echo "** Stopping database ${DBNAME}..."
    ./stop-database.sh ${DBNAME}
  fi
done

echo "** Stoping storage services..."
cat data/hosts-static | while read DBHOST; do
  if [[ ! -z "$DBHOST" ]]; then
    echo "Stopping storage on ${DBHOST}..."
    ssh ${REMOTE_USER}'@'${DBHOST} sudo systemctl stop ${SVC_STATIC} </dev/null
  fi
done
