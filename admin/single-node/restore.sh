#!/usr/bin/env bash
#
# YDB restore script using 'ydb tools restore'.
# Restores from a squashfs backup archive. If no backup ID is given, uses the latest.
# Uses settings from env.vars.
#
# Usage:
#   ./restore.sh [BACKUP_ID]
#
# Arguments:
#   BACKUP_ID   - Optional. Backup ID (timestamp) of the backup to restore.
#                 If omitted, restores from the latest backup.
#
# Prerequisites:
#   sudo apt install squashfuse
#

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

set -o allexport
. ./env.vars
set +o allexport

readonly BACKUPS_DIR="./backups"
readonly RESTORE_MOUNT="./restore"

resolve_backup_id() {
    local backup_id="${1:-}"

    if [[ -z "$backup_id" ]]; then
        if [[ ! -d "$BACKUPS_DIR" ]]; then
            echo "** Backups directory does not exist: ${BACKUPS_DIR}" >&2
            exit 1
        fi
        backup_id=$(find "$BACKUPS_DIR" -maxdepth 1 -type f -name "*.squashfs" -exec basename {} .squashfs \; 2>/dev/null | sort -r | head -n1)
        if [[ -z "$backup_id" ]]; then
            echo "** No backups found in ${BACKUPS_DIR}" >&2
            exit 1
        fi
        echo "** No backup ID specified, using latest: ${backup_id}" >&2
    fi

    echo "$backup_id"
}

backup_id=$(resolve_backup_id "${1:-}")
backup_archive="${BACKUPS_DIR}/${backup_id}.squashfs"

if [[ ! -f "$backup_archive" ]]; then
    echo "** Backup archive does not exist: ${backup_archive}" >&2
    exit 1
fi

echo "** Starting restore from ${backup_archive}" >&2

mkdir -pv "$RESTORE_MOUNT"

cleanup() {
    fusermount -u "$RESTORE_MOUNT" 2>/dev/null || true
}
trap cleanup EXIT

squashfuse "$backup_archive" "$RESTORE_MOUNT"

if ! YDB_PASSWORD="${YDB_ROOT_PASSWORD}" ./app/ydb -e "grpcs://${YDB_HOST}:2135" \
        -d /local --ca-file certs/ca.crt --user root \
        tools restore -p . -i "${RESTORE_MOUNT}" --import-data; then
    echo "** Restore failed" >&2
    exit 1
fi

echo "** Restore completed successfully from ${backup_id}" >&2
