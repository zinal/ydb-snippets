# Инструменты для автоматизации операций через Embedded UI

## Аутентификация

Для YDB со статической аутентификацией доступ из скриптов в Embedded UI требует наличия токена. Токен берётся из Cookie `ydb_session_id` и сохраняется в файл `~/.ydb/token`.

Получить токен автоматически можно скриптом `get_token.py` (логин/пароль из переменных `YDB_USER` и `YDB_PASSWORD`, запрос `POST /login`):

```bash
export YDB_USER=root
export YDB_PASSWORD='...'
./get_token.py --viewer-url https://ycydb-s1:8765
```

Вручную токен можно взять из Cookie `ydb_session_id` в интерфейсе Embedded UI. Для версий YDB ранее 26.1 альтернативно можно обратиться к адресу `https://localhost:8765/viewer/json/whoami` (вместо `localhost:8765` укажите корректный адрес Embedded UI) — токен будет в поле `OriginalUserToken`.

## Поиск таблиц в legacy-режиме

Скрипт `find_legacy_tables.py` обходит схему через `/scheme/directory` (рекурсивно, с обходом каждого каталога) и для каждой таблицы проверяет `/viewer/json/describe?partition_config=true`.

Таблица считается legacy, если у `PathDescription.Table.PartitionConfig` нет family с `Id: 0` или у family 0 нет `StorageConfig`.

Аутентификация: `--auth Login` и токен в `~/.ydb/token` (авто-логин не используется).

```bash
# Полная проверка всех таблиц БД
./find_legacy_tables.py --viewer-url https://somehost:8765 --auth Login \
  /Root/database

# Только поддерево под schema1
./find_legacy_tables.py  --viewer-url https://somehost:8765 --auth Login \
  --path /Root/database/schema1 /Root/database
```

В stdout печатаются только legacy-таблицы (`path` и причина через табуляцию). Прогресс и итог — в stderr.

## Принудительная компактификация таблеток

```bash
export YDB_USER=root
export YDB_PASSWORD='...'
./get_token.py --viewer-url https://ycydb-s1:8765

# Table compaction
./table_full_compact.py --viewer-url https://ycydb-s1:8765 --auth Login --all /Domain0/tpcc/order_line
```

## Принудительная дефрагментация VDisk

Скрипт `vdisk_compact.py` реализует операции полной принудительной дефрагментации VDisk:

- compact: `type=dbmainpage&action=compact` (аналог операции `ydb-dstool vdisk compact`)
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

Рекомендуемый порядок действий для полной дефрагментации VDisk в конкретной БД:

```bash
# Адрес сервера и имя пула хранения
YDB_URL=https://ycydb-s1:8765
YDB_POOL=/Root/testdb:ssd

# 1. Дефрагментация
./vdisk_compact.py --viewer-url ${YDB_URL} --auth Login --mode defrag  --pool ${YDB_POOL} --threads 8

# 2. Полная компактификация
./vdisk_compact.py --viewer-url ${YDB_URL} --auth Login --mode compact-full --pool ${YDB_POOL} --threads 8

# 3. Повторная дефрагментация
./vdisk_compact.py --viewer-url ${YDB_URL} --auth Login --mode defrag  --pool ${YDB_POOL} --threads 16

# 4. Пауза 10 секунд
sleep 10

# 5. Повторная полная дефрагментация
./vdisk_compact.py --viewer-url ${YDB_URL} --auth Login --mode compact-full --pool ${YDB_POOL} --threads 8
```

Другие примеры вызовов:

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
