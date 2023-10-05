#! /bin/bash

set -e
set -u

. ./options.sh

DB_DOMAIN=/${YDB_DOMAIN}

run_discovery() {
  DB_ENDPOINT="grpcs://$1":${YDB_STORAGE_PORT}
  if [ -z "$YDB_PASSWORD" ]; then
    ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d ${DB_DOMAIN} \
      --user root --no-password discovery list >/dev/null 2>&1
  else
    ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d ${DB_DOMAIN} discovery list >/dev/null 2>&1
  fi
}

run_discovery_all() {
  cat data/hosts-static | while read DBHOST; do
    if [ ! -z "$DBHOST" ]; then
      if ! run_discovery ${DBHOST}; then
        return 1
      fi
    fi
  done
}

echo "Waiting for storage nodes to come up..."

set +e

COUNTER=0
while true; do
    if run_discovery_all; then
        echo "Storage nodes are all ONLINE."
        exit 0
    fi
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt 36 ]; then
        if run_discovery_all; then
            echo "Storage nodes are all ONLINE."
            exit 0
        fi
        echo "ERROR: some storage nodes did not appear in 3 minutes" >&2
        exit 1
    fi
    sleep 5
done
