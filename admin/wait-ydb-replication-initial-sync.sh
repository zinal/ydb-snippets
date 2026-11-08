#!/bin/bash
# Ждёт окончания начальной синхронизации асинхронной репликации YDB
# по всем таблицам.
#
# Использование:
#   wait-ydb-replication-initial-sync.sh [-i СЕКУНДЫ] [-n ПОВТОРЫ] ПРОФИЛЬ ИМЯ
#
# Опрашивает:
#   ydb -p ПРОФИЛЬ scheme describe ИМЯ --stats --format proto-json-base64
#
# Ответ — protobuf DescribeReplicationResult с исходными именами полей.
# Начальный скан таблицы ещё идёт, если у элемента
# items[].stats.initial_scan_progress меньше 100. После завершения скана
# сервер перестаёт присылать это поле (прогресс берётся из changefeed
# источника только пока у потока есть ScanProgress). Сводный
# running.stats.initial_scan_progress есть только когда скан ещё
# сообщают все таблицы сразу.
#
# Репликация в состоянии paused (INITIAL_SCAN = FALSE) начальный скан
# не выполняет: скрипт продолжает ждать, пока её не переведут в running.
# Состояние error — немедленный выход с кодом 1. Состояние done
# (репликация уже завершена целиком) — выход с кодом 0.
#
# Чтобы не выйти в короткое окно, когда changefeed уже создан, а процент
# скана ещё не опубликован, «чистое» наблюдение должно повториться
# несколько раз подряд (-n, по умолчанию 3). Появление новой таблицы
# или прогресса < 100 сбрасывает счётчик.

set -euo pipefail

INTERVAL=5
CONFIRM=3
MAX_CLI_ERRORS=30

usage() {
  cat <<'EOF'
Использование: wait-ydb-replication-initial-sync.sh [-i СЕКУНДЫ] [-n ПОВТОРЫ] ПРОФИЛЬ ИМЯ

Ждёт, пока начальная синхронизация асинхронной репликации завершится
по всем таблицам (включая таблицы реализации индексов).

  ПРОФИЛЬ    имя профиля YDB CLI базы-приёмника
  ИМЯ        путь объекта ASYNC REPLICATION в этой базе
  -i СЕКУНДЫ пауза между опросами (по умолчанию 5)
  -n ПОВТОРЫ сколько опросов подряд без незавершённого скана нужно
             увидеть перед выходом (по умолчанию 3)

Код 0 — начальная синхронизация завершена (или репликация уже в done).
Код 1 — репликация в состоянии error, объект не является репликацией
или опрос YDB CLI не удался.
EOF
}

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "$*" >&2
  exit 1
}

while getopts ":i:n:h" opt; do
  case "$opt" in
    i) INTERVAL=$OPTARG ;;
    n) CONFIRM=$OPTARG ;;
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
if ! [[ "$CONFIRM" =~ ^[0-9]+$ ]] || [[ "$CONFIRM" -lt 1 ]]; then
  echo "число повторов должно быть целым числом >= 1" >&2
  exit 2
fi

PROFILE=$1
REPLICATION=$2

command -v ydb >/dev/null 2>&1 || { echo "не найден ydb в PATH" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "не найден jq в PATH" >&2; exit 2; }

# action: wait | confirm | success | fail
READ_REPLICATION='
def num(v):
  if v == null then null
  elif (v | type) == "number" then v
  elif (v | type) == "string" and (v | test("^-?[0-9]+(\\.[0-9]+)?$")) then (v | tonumber)
  else null
  end;
def item_progress:
  num(.stats.initial_scan_progress // .stats.initialScanProgress);
def item_name:
  (.destination_path // .destinationPath // .source_path // .sourcePath // "?");
def item_cf:
  (.source_changefeed_name // .sourceChangefeedName // "");
def scanning:
  (item_progress != null and item_progress < 100);
def fmt_progress:
  if item_progress == null then "скан не сообщается"
  else (item_progress | tostring) + "%"
  end;
def entry_type:
  (.self.type // .self.Type // "");
def state_name:
  if has("error") then "error"
  elif has("done") then "done"
  elif has("paused") then "paused"
  elif has("running") then "running"
  else "unknown"
  end;
def items:
  (.items // []);
def running_progress:
  num(.running.stats.initial_scan_progress // .running.stats.initialScanProgress);
def issues:
  ((.error.issues // []) | map(.message // empty) | join("; "));
def lines:
  [ items[] | "\(item_name): \(fmt_progress)" ];
(entry_type) as $type
| (state_name) as $state
| (items) as $items
| ([$items[] | select(item_cf == "")] | length) as $missing_cf
| ([$items[] | select(scanning)] | length) as $scanning
| (running_progress) as $running_progress
| (issues) as $issues
| (lines) as $lines
| if ($type != "" and $type != "REPLICATION" and $type != 16) then
    {action: "fail", detail: "объект типа \($type), ожидается ASYNC REPLICATION", lines: []}
  elif ($state == "unknown" and ($items | length) == 0) then
    {action: "fail", detail: "ответ не похож на описание асинхронной репликации", lines: []}
  elif $state == "error" then
    {action: "fail", detail: ("репликация в состоянии error" + (if $issues != "" then ": " + $issues else "" end)), lines: $lines}
  elif $state == "done" then
    {action: "success", detail: "репликация уже в состоянии done", lines: $lines}
  elif $state == "paused" then
    {action: "wait", detail: "состояние paused, начальный скан ещё не запущен", lines: $lines}
  elif ($items | length) == 0 then
    {action: "wait", detail: "список таблиц ещё пуст", lines: []}
  elif $missing_cf > 0 then
    {action: "wait", detail: "changefeed ещё не создан у \($missing_cf) из \($items | length)", lines: $lines}
  elif $scanning > 0 or ($running_progress != null and $running_progress < 100) then
    {action: "wait", detail: "начальный скан: \($scanning) из \($items | length) таблиц", lines: $lines}
  else
    {action: "confirm", detail: "незавершённого скана нет, таблиц \($items | length)", lines: $lines}
  end
'

is_fatal_cli_error() {
  printf '%s' "$1" | grep -Eiq \
    'NOT_FOUND|not found|Misuse|unknown profile|no profile|Unknown command|No such file|does not exist'
}

ERR_FILE=$(mktemp)
trap 'rm -f "$ERR_FILE"' EXIT

cli_errors=0
stable=0
log "ожидание начальной синхронизации ${REPLICATION} (профиль ${PROFILE})"

while true; do
  set +e
  stdout=$(ydb -p "$PROFILE" scheme describe "$REPLICATION" --stats --format proto-json-base64 2>"$ERR_FILE")
  rc=$?
  set -e
  stderr=$(cat "$ERR_FILE")

  if [[ $rc -ne 0 ]]; then
    cli_errors=$((cli_errors + 1))
    stable=0
    log "ydb scheme describe завершился с кодом ${rc} (${cli_errors}/${MAX_CLI_ERRORS})" >&2
    if [[ -n "$stderr" ]]; then
      printf '%s\n' "$stderr" >&2
    fi
    if [[ -n "$stdout" ]]; then
      printf '%s\n' "$stdout" >&2
    fi
    if is_fatal_cli_error "${stderr}"$'\n'"${stdout}"; then
      die "опрос остановлен: репликация или профиль недоступны"
    fi
    if [[ $cli_errors -ge $MAX_CLI_ERRORS ]]; then
      die "слишком много ошибок ydb подряд"
    fi
    sleep "$INTERVAL"
    continue
  fi
  cli_errors=0

  if ! summary=$(printf '%s\n' "$stdout" | jq -ce "$READ_REPLICATION"); then
    die "не удалось разобрать ответ ydb scheme describe: ${stdout}"
  fi

  action=$(printf '%s\n' "$summary" | jq -r '.action')
  detail=$(printf '%s\n' "$summary" | jq -r '.detail')

  case "$action" in
    fail)
      die "$detail"
      ;;
    success)
      log "$detail"
      printf '%s\n' "$summary" | jq -r '.lines[]?'
      exit 0
      ;;
    wait)
      stable=0
      log "$detail"
      printf '%s\n' "$summary" | jq -r '.lines[]?'
      ;;
    confirm)
      stable=$((stable + 1))
      log "${detail} (${stable}/${CONFIRM})"
      printf '%s\n' "$summary" | jq -r '.lines[]?'
      if [[ "$stable" -ge "$CONFIRM" ]]; then
        log "начальная синхронизация завершена по всем таблицам"
        exit 0
      fi
      ;;
    *)
      die "неизвестное решение разбора: ${action}"
      ;;
  esac

  sleep "$INTERVAL"
done
