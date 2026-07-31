# Инструменты для автоматизации операций через Embedded UI

## Аутентификация

Для YDB со статической аутентификацией доступ из скриптов в Embedded UI требует наличия токена. Токен можно получить из Cookie с идентификатором `ydb_session_id`, зайдя в интерфейс Embedded UI. Для версий YDB ранее 26.1 альтернативно можно обратиться к следующему адресу: https://localhost:8765/viewer/json/whoami (место `localhost:8765` должен быть указан корректный адрес доступа к Embedded UI), токен будет в поле `OriginalUserToken`.

Полученный токен необходимо поместить в файл `~/.ydb/token`

## Принудительная компактификация таблеток

```bash
mkdir ~/.ydb
vi ~/.ydb/token

# Table compaction
./table_full_compact.py --viewer-url https://ycydb-s1:8765 --auth Login --all /Domain0/tpcc/order_line
```

## Принудительная компактификация / дефрагментация VDisk

Скрипт `vdisk_compact.py` работает через Embedded UI mon-страницы VDisk:

- compact: `type=dbmainpage&action=compact` (аналог `ydb-dstool vdisk compact`)
- defrag: `type=dbmainpage&dbname=LogoBlobs&action=defrag`

Режим задаётся одной опцией `--mode`:

| `--mode` | Действие |
| --- | --- |
| `compact-full` | Compact LogoBlobs + Blocks + Barriers (по умолчанию) |
| `compact-logoblobs` | Compact LogoBlobs |
| `compact-blocks` | Compact Blocks |
| `compact-barriers` | Compact Barriers |
| `defrag` | Defrag LogoBlobs |

Аутентификация такая же, как у остальных скриптов в этом каталоге: `--auth Login` и токен в `~/.ydb/token`.

```bash
# Полная компактификация конкретных VDisk (форматы id как в ydb-dstool)
./vdisk_compact.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --mode compact-full --vdisk-ids '[00000001:1:0:0:0]' '[00000001:1:0:1:0]'

# Все VDisk пула хранения: группы параллельно, внутри группы последовательно
./vdisk_compact.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --mode compact-full --pool /Root:ssd --threads 8

# Отдельный прогон дефрагментации
./vdisk_compact.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --mode defrag --pool /Root:ssd --threads 8

# Только показать цели без запуска
./vdisk_compact.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --mode compact-full --pool /Root:ssd --dry-run

# Подробный лог по каждому VDisk / ожиданию
./vdisk_compact.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --mode compact-full --pool /Root:ssd --threads 8 --debug
```

По умолчанию печатается общий прогресс (`done` / `remaining` / процент). Детали запросов и ожидания — только с `--debug`. Перед запуском VDisk сортируются по идентификатору группы.
