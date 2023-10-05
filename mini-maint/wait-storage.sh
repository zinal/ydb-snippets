#! /bin/sh

set -e
set -u

. ./options.sh

DB_ENDPOINT='grpcs://'`head -n 1 data/hosts-static`:${YDB_STORAGE_PORT}
DB_DOMAIN=/${YDB_DOMAIN}

run_discovery() {
  if [ -z "${YDB_PASSWORD}" ]; then
    ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d ${DB_DOMAIN} \
      --user root --no-password monitoring healthcheck --format json >/dev/null 2>&1
  else
    ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d ${DB_DOMAIN} monitoring healthcheck --format json >/dev/null 2>&1
  fi
}

echo "Waiting for storage startup..."

COUNTER=0
while true; do
    if run_discovery; then
        echo "Storage is ONLINE."
        exit 0
    fi
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt 36 ]; then
        if run_discovery; then
            echo "Storage is ONLINE."
            exit 0
        fi
        echo "ERROR: storage did not appear in 3 minutes" >&2
        exit 1
    fi
    sleep 5
done
