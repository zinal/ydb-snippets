#! /bin/sh

set -e
set -u

set -o allexport
. ./env.vars
set +o allexport

# TODO: ensure that the server is stopped

echo "${YDB_HOST}" >ydb-ca-nodes.txt
./ydb-ca-update.sh

CERT_DIR=`ls CA/certs | grep -E '^2.*' | sort | tail -n 1`
cp -v CA/certs/${CERT_DIR}/ca.crt certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/node.crt certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/node.key certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/web.pem certs/
chmod -v 600 certs/*

./app/ydbd admin bs disk obliterate ${YDB_DISK}

envsubst <config.yaml.template >config/config.yaml

#./start.sh

echo "Completed, ready to go!"
