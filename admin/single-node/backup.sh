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

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

set -o allexport
. ./env.vars
set +o allexport

local backup_id
backup_id=$(date -u +%Y%m%d-%H%M%S)
local backup_subdir="backups/${backup_id}"

mkdir -pv "$backup_subdir"
echo "Starting backup to ${backup_subdir}" >&2

if ! YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e "grpcs://${YDB_HOST}:2135" \
        -d /local --ca-file certs/ca.crt --user root \
        -vv tools dump -p . -o "${backup_subdir}"; then
    rm -rf -- "${backup_subdir}"
    echo "Backup failed" >&2
    exit 1
fi

echo "Backup completed successfully: ${backup_id}" >&2
echo "${backup_id}"
