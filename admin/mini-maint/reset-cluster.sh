#! /bin/bash

ASKYES=$1
if [ -z "$ASKYES" ]; then
  echo "USAGE: $0 yes-really-do-it"
  exit
fi

set -e
set -u

. ./options.sh

echo "*** Cluster cleanup started (ALL DATA WILL BE LOST)..."

ydb version --disable-checks

./stop-cluster.sh

echo "** Re-formatting disks..."
cat data/hosts-static | while read DBHOST; do
  if [[ ! -z "$DBHOST" ]]; then
    cat data/disks | while read DBDISK; do
      if [[ ! -z "$DBDISK" ]]; then
        echo "...${DBHOST} -> ${DBDISK}"
        ssh ${REMOTE_USER}'@'${DBHOST} "sudo LD_LIBRARY_PATH=${REMOTE_YDB}/lib ${REMOTE_YDB}/bin/ydbd admin bs disk obliterate ${DBDISK}" </dev/null
      fi
    done
  fi
done

./start-storage.sh

YDB_PASSWORD='' ./wait-storage-nodes.sh

echo "** Authenticating..."
DB_ENDPOINT='grpcs://'`head -n 1 data/hosts-static`:${YDB_STORAGE_PORT}
TOKEN=`mktemp /tmp/ydbd.token.XXXXXX`
trap "rm -f ${TOKEN}" EXIT
ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d /${YDB_DOMAIN} \
  --user root --no-password auth get-token -f > ${TOKEN}

echo "** Initializing storage..."
ydbd --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -s ${DB_ENDPOINT} -f ${TOKEN} \
  admin blobstorage config init --yaml-file ${YDB_CONFIG}

YDB_PASSWORD='' ./wait-storage.sh

echo "Re-setting password..."
ydb --ca-file ${YDB_SSL_ROOT_CERTIFICATES_FILE} -e ${DB_ENDPOINT} -d /${YDB_DOMAIN} --user root --no-password \
  yql -s 'ALTER USER root PASSWORD "'${YDB_PASSWORD}'";'

echo "** All good, time to create databases!"
