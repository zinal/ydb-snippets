#! /bin/bash

DBNAME="$1"

if [ -z "$DBNAME" ]; then
  echo "USAGE: $0 DBNAME"
  exit 1
fi

set -e
set -u

. ./options.sh

startNode() {
  DBHOST="$1"
  cat data/svc-db-${DBNAME} | while read DBSVC DBPORT; do
    if [[ ! -z "$DBSVC" ]]; then
      echo "...${DBSVC}"
      ssh ${REMOTE_USER}'@'${DBHOST} sudo systemctl start ${DBSVC} </dev/null
    fi
  done
}

cat data/hosts-db-${DBNAME} | while read DBHOST; do
  if [[ ! -z "$DBHOST" ]]; then
    echo "Starting services on ${DBHOST}..."
    startNode ${DBHOST}
  fi
done
