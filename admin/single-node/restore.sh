#!/usr/bin/env bash
#
# YDB restore script using 'ydb tools restore'.
# Restores from a backup subdirectory. If no backup ID is given, uses the latest.
# Uses settings from env.vars.
#
# Usage:
#   ./restore.sh [BACKUP_ID]
#
# Arguments:
#   BACKUP_ID   - Optional. Subdirectory name (timestamp) of the backup to restore.
#                 If omitted, restores from the latest backup.
#

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

set -o allexport
. ./env.vars
set +o allexport

readonly BACKUPS_DIR="./backups"

resolve_backup_id() {
    local backup_id="${1:-}"

    if [[ -z "$backup_id" ]]; then
        if [[ ! -d "$BACKUPS_DIR" ]]; then
            echo "Backups directory does not exist: ${BACKUPS_DIR}" >&2
            exit 1
        fi
        backup_id=$(find "$BACKUPS_DIR" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort -r | head -n1)
        if [[ -z "$backup_id" ]]; then
            echo "No backups found in ${BACKUPS_DIR}" >&2
            exit 1
        fi
        echo "No backup ID specified, using latest: ${backup_id}" >&2
    fi

    echo "$backup_id"
}

local backup_id
backup_id=$(resolve_backup_id "${1:-}")

local backup_subdir="${BACKUPS_DIR}/${backup_id}"

if [[ ! -d "$backup_subdir" ]]; then
    echo "Backup directory does not exist: ${backup_subdir}" >&2
    exit 1
fi

echo "Starting restore from ${backup_subdir}" >&2

if ! YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e "grpcs://${YDB_HOST}:2135" \
        -d /local --ca-file certs/ca.crt --user root \
        tools restore -p . -i "${backup_subdir}" --import-data; then
    echo "Restore failed" >&2
    exit 1
fi

echo "Restore completed successfully from ${backup_id}" >&2
