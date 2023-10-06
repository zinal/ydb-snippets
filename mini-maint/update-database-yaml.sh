#! /bin/bash

DBNAME="$1"
LOCAL_YAML="$2"

if [ -z "$DBNAME" ] || [ -z "$LOCAL_YAML" ] || [ ! -f "$LOCAL_YAML" ]; then
  echo "USAGE: $0 DBNAME FILE.YAML"
  exit 1
fi

set -e
set -u

. ./options.sh

updateYaml() {
  YAML=$1
  DBHOST=$2
  scp ${LOCAL_YAML} ${REMOTE_USER}'@'${DBHOST}:/tmp/
  ssh ${REMOTE_USER}'@'${DBHOST} sudo mv /tmp/${LOCAL_YAML} ${REMOTE_YDB}/cfg/${YAML} </dev/null
  ssh ${REMOTE_USER}'@'${DBHOST} sudo chown root:root ${REMOTE_YDB}/cfg/${YAML} </dev/null
}

doIt() {
  YAML=$1
  cat data/hosts-db-${DBNAME} | while read DBHOST; do
    if [[ ! -z "$DBHOST" ]]; then
      echo "Updating ${YAML} on ${DBHOST}..."
      updateYaml ${YAML} ${DBHOST}
    fi
  done
}

FOUNDIT=0
cat data/databases | while read DBNAME1 YAML; do
  if [ "$DBNAME" = "$DBNAME1" ]; then
    doIt "$YAML"
    FOUNDIT=1
  fi
done
