#! /bin/bash

set -e
set -u

. ./options.sh

DBNAME="$1"

stopNode() {
  DBHOST="$1"
  cat data/svc-db-${DBNAME} | while read DBSVC DBPORT; do
    if [[ ! -z "$DBSVC" ]]; then
      echo "...${DBSVC}"
      ssh ${REMOTE_USER}'@'${DBHOST} sudo systemctl stop ${DBSVC}
    fi
  done
}

cat data/hosts-db-${DBNAME} | while read DBHOST; do
  if [[ ! -z "$DBHOST" ]]; then
    echo "Stopping services on ${DBHOST}..."
    stopNode ${DBHOST}
  fi
done
