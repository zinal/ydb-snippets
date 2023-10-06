#! /bin/bash

DB_NAME=$1
DB_POOL=ssd
DB_GROUPS=$2

if [ -z "$DB_NAME" ] || [ -z "$DB_GROUPS" ]; then
  echo "USAGE: $0 DBNAME N"
  exit 1
fi

set -e
set -u

. ./options.sh

./wait-storage-nodes.sh

echo "** Authenticating..."
DB_ENDPOINT='grpcs://'`head -n 1 data/hosts-static`:${YDB_STORAGE_PORT}
TOKEN=`mktemp /tmp/ydbd.token.XXXXXX`
trap "rm -f ${TOKEN}" EXIT
ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d /${YDB_DOMAIN} \
  auth get-token -f > ${TOKEN}

TMPLOG=`mktemp /tmp/ydbd.createdb.XXXXXX`
trap "rm -f ${TMPLOG}" EXIT

echo "** Creating database ${DB_NAME}..."
ydbd --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -s ${DB_ENDPOINT} -f ${TOKEN} \
  admin database /${YDB_DOMAIN}/${DB_NAME} create ${DB_POOL}:${DB_GROUPS} >>${TMPLOG} 2>&1

# Ensure success, e.g. no error messages even when the exit code is zero.
set +e
if grep -qE '^ERROR: ' ${TMPLOG}; then
  cat ${TMPLOG};
  exit 1
fi
echo "...success!"
exit 0
