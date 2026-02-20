#!/usr/bin/env bash
#
# YDB backup script using 'ydb tools dump'.
# Each backup is stored in a timestamped subdirectory under backups/.
# Uses settings from env.vars.
#
# Usage:
#   ./backup.sh
#

set -euo pipefail

readonly SCRIPT_DIR=$(cd $(dirname $0) && pwd)
cd "$SCRIPT_DIR"

set -o allexport
. ./env.vars
set +o allexport

backup_id=$(date -u +%Y%m%d-%H%M%S)
backup_subdir="backups/${backup_id}"

mkdir -pv "$backup_subdir"
echo "** Starting export to ${backup_subdir}" >&2

if ! YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e "grpcs://${YDB_HOST}:${YDB_PORT_APP}" \
        -d "/${YDB_DOMAIN_NAME}" --ca-file certs/ca.crt --user root \
        -vv tools dump --exclude '^/'"${YDB_DOMAIN_NAME}"'/[.]sys' -p . -o "${backup_subdir}"; then
    rm -rf -- "${backup_subdir}"
    echo "** Backup failed" >&2
    exit 1
fi

echo "** Export completed successfully: ${backup_id}" >&2

mksquashfs "${backup_subdir}" "${backup_subdir}.squashfs" -comp zstd
rm -rf -- "${backup_subdir}"

echo "** Export archived successfully: ${backup_id}.squashfs" >&2

echo "${backup_id}"
