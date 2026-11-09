#!/bin/bash
# Ждёт завершения операции экспорта или импорта YDB.
#
# Использование:
#   wait-ydb-operation.sh [-i СЕКУНДЫ] ПРОФИЛЬ ID_ОПЕРАЦИИ
#
# Опрашивает:
#   ydb -p ПРОФИЛЬ operation get --format proto-json-base64 ID_ОПЕРАЦИИ
#
# CLI печатает protobuf Ydb.Operations.Operation одним JSON-объектом
# (camelCase, бинарные поля в Base64). Пока операция идёт, поле ready
# отсутствует: proto3 не выводит false. status=SUCCESS бывает и у ещё
# выполняющейся операции, поэтому конец — только ready=true.
# Прогресс экспорта/импорта лежит в metadata.progress:
#   PROGRESS_PREPARING, PROGRESS_TRANSFER_DATA, PROGRESS_BUILD_INDEXES,
#   PROGRESS_CREATE_CHANGEFEEDS, PROGRESS_CANCELLATION,
#   PROGRESS_DONE, PROGRESS_CANCELLED.
#
# Код выхода: 0 — операция завершилась со status=SUCCESS, 1 — ошибка,
# отмена или сбой опроса, 2 — неверные аргументы.

set -euo pipefail

INTERVAL=5
MAX_CLI_ERRORS=30

usage() {
  cat <<'EOF'
Использование: wait-ydb-operation.sh [-i СЕКУНДЫ] ПРОФИЛЬ ID_ОПЕРАЦИИ

Ждёт завершения операции экспорта или импорта.
ID_ОПЕРАЦИИ — строка вида ydb://export/6?id=...&kind=s3 (нужны кавычки в shell).

  -i СЕКУНДЫ   пауза между опросами (по умолчанию 5)

Код 0 — status=SUCCESS. Код 1 — операция завершилась ошибкой или отменой.
EOF
}

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "$*" >&2
  exit 1
}

while getopts ":i:h" opt; do
  case "$opt" in
    i) INTERVAL=$OPTARG ;;
    h)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -lt 1 ]]; then
  echo "интервал должен быть целым числом >= 1" >&2
  exit 2
fi

PROFILE=$1
OPERATION_ID=$2

command -v ydb >/dev/null 2>&1 || { echo "не найден ydb в PATH" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "не найден jq в PATH" >&2; exit 2; }

# Готовый объект для решения, завершилась ли операция.
READ_OPERATION='{
  ready: (.ready == true),
  status: (.status // "STATUS_CODE_UNSPECIFIED"),
  progress: (.metadata.progress // .progress // "unknown"),
  parts_completed: (
    (.metadata.itemsProgress // .metadata.items_progress // [])
    | map(.partsCompleted // .parts_completed // 0)
    | add // 0
  ),
  parts_total: (
    (.metadata.itemsProgress // .metadata.items_progress // [])
    | map(.partsTotal // .parts_total // 0)
    | add // 0
  ),
  issues: ((.issues // []) | map(.message // empty) | join("; "))
}'

is_fatal_cli_error() {
  printf '%s' "$1" | grep -Eiq \
    'NOT_FOUND|not found|Invalid operation|Misuse|unknown profile|no profile|Unknown command|No such file'
}

ERR_FILE=$(mktemp)
trap 'rm -f "$ERR_FILE"' EXIT

cli_errors=0
log "ожидание операции ${OPERATION_ID} (профиль ${PROFILE})"

while true; do
  set +e
  stdout=$(ydb -p "$PROFILE" operation get --format proto-json-base64 "$OPERATION_ID" 2>"$ERR_FILE")
  rc=$?
  set -e
  stderr=$(cat "$ERR_FILE")

  if [[ $rc -ne 0 ]]; then
    cli_errors=$((cli_errors + 1))
    log "ydb operation get завершился с кодом ${rc} (${cli_errors}/${MAX_CLI_ERRORS})" >&2
    if [[ -n "$stderr" ]]; then
      printf '%s\n' "$stderr" >&2
    fi
    if [[ -n "$stdout" ]]; then
      printf '%s\n' "$stdout" >&2
    fi
    if is_fatal_cli_error "${stderr}"$'\n'"${stdout}"; then
      die "опрос остановлен: операция или профиль недоступны"
    fi
    if [[ $cli_errors -ge $MAX_CLI_ERRORS ]]; then
      die "слишком много ошибок ydb подряд"
    fi
    sleep "$INTERVAL"
    continue
  fi
  cli_errors=0

  if ! summary=$(printf '%s\n' "$stdout" | jq -ce "$READ_OPERATION"); then
    die "не удалось разобрать ответ ydb operation get: ${stdout}"
  fi

  ready=$(printf '%s\n' "$summary" | jq -r '.ready')
  status=$(printf '%s\n' "$summary" | jq -r '.status')
  progress=$(printf '%s\n' "$summary" | jq -r '.progress')
  parts_completed=$(printf '%s\n' "$summary" | jq -r '.parts_completed')
  parts_total=$(printf '%s\n' "$summary" | jq -r '.parts_total')
  issues=$(printf '%s\n' "$summary" | jq -r '.issues')

  parts=""
  if [[ "$parts_total" != "0" ]]; then
    parts=" parts=${parts_completed}/${parts_total}"
  fi

  if [[ "$ready" == "true" ]]; then
    if [[ "$status" == "SUCCESS" ]]; then
      log "операция завершена: status=${status} progress=${progress}${parts}"
      exit 0
    fi
    log "операция завершилась с ошибкой: status=${status} progress=${progress}${parts}" >&2
    if [[ -n "$issues" ]]; then
      log "issues: ${issues}" >&2
    fi
    exit 1
  fi

  log "операция выполняется: progress=${progress} status=${status}${parts}"
  sleep "$INTERVAL"
done
