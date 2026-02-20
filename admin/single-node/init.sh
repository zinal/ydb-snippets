#! /usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"
set -o allexport
. ./env.vars
set +o allexport

echo "** Shutting down database..."
./stop.sh

echo "** Updating TLS certificates..."
echo "${YDB_HOST}" >ydb-ca-nodes.txt
./ydb-ca-update.sh

mkdir -pv certs

CERT_DIR=`ls CA/certs | grep -E '^2.*' | sort | tail -n 1`
cp -v CA/certs/${CERT_DIR}/ca.crt certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/node.crt certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/node.key certs/
cp -v CA/certs/${CERT_DIR}/${YDB_HOST}/web.pem certs/
chmod -v 600 certs/*

echo "** Generating configuration file..."
mkdir -pv config
envsubst <config.yaml.template >config/config.yaml

echo "** Cleaning disk..."
./app/ydbd admin bs disk obliterate ${YDB_DISK}

echo "** Starting database process..."
mkdir -pv logs
./start.sh
sleep 5

SERVER_PID=`cat logs/server.pid`
set +e
if kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    echo "** ydbd running, moving forward..."
else
    echo "** ydbd NOT running, exiting! Check the logs."
    exit 1
fi
set -e

YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e grpcs://${YDB_HOST}:2135 \
            -d "/${YDB_DOMAIN_NAME}" --ca-file certs/ca.crt --user root auth get-token -f \
            > ydb-token
echo "** Authentication token obtained."

./app/ydbd -s grpcs://localhost:2135 --ca-file certs/ca.crt --token-file ydb-token \
           admin bs config init --yaml-file config/config.yaml
echo "** Storage initialization successful."

./app/ydbd -s grpcs://localhost:2135 --ca-file certs/ca.crt --token-file ydb-token \
           admin bs config invoke --proto-file=command-storage-pools.proto
echo "** Storage pool created."

./app/ydbd -s grpcs://localhost:2135 --ca-file certs/ca.crt --token-file ydb-token \
           db schema execute command-domain.proto
echo "** Storage pool assigned."

YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e grpcs://${YDB_HOST}:2135 \
            -d "/${YDB_DOMAIN_NAME}" --ca-file certs/ca.crt --user root sql -s \
            'ALTER GROUP `ADMINS` ADD USER ${YDB_CUSTOM_LOGIN};'
echo "** User ${YDB_CUSTOM_LOGIN} has been granted the admin role."

echo "** Completed, ready to go!"
