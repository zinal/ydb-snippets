#! /bin/bash

set -e
set -u

. ./options.sh

SVC_STATIC=`cat data/svc-static`

echo "** Starting storage services..."
cat data/hosts-static | while read DBHOST; do
  if [[ ! -z "$DBHOST" ]]; then
    echo "Starting storage on ${DBHOST}..."
    ssh ${REMOTE_USER}'@'${DBHOST} sudo systemctl start ${SVC_STATIC} </dev/null
  fi
done
