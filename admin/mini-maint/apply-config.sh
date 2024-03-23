#! /bin/bash

CONFFILE=$1

if [ -z "$CONFFILE" ] || [ ! -f "$CONFFILE" ]; then
  echo "USAGE: $0 CONFFILE"
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

echo "** Applying config protobuf file ${CONFFILE}..."
ydbd --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -s ${DB_ENDPOINT} -f ${TOKEN} \
  admin console configs update ${CONFFILE}
