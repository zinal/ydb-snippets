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

## Остановка и запуск таблеток по типу объекта

Скрипт `manage_tablets.py` останавливает или запускает таблетки схемных объектов выбранного вида. По умолчанию вид `PQ`: объекты типа topic (`TOPIC` и устаревший `PERS_QUEUE_GROUP`), а также служебные топики CDC. Для каждого топика в операцию попадают таблетки партиций (тип PersQueue) и таблетка read balancer. Партиции в статусе `Deleted` пропускаются.

Топик CDC не лежит в каталоге рядом с таблицами. Schemeshard создаёт его как `{таблица}/{changefeed}/streamImpl`. При `--type PQ` скрипт описывает таблицы под префиксом, читает `PathDescription.Table.CdcStreams` и берёт PersQueue-детей этого потока (обычно `streamImpl`).

Вторичный индекс тоже не виден в каталоге. Его даташарды принадлежат таблице реализации, обычно `{таблица}/{индекс}/indexImplTable` (у векторного или полнотекстового индекса таких таблиц несколько, их имена берутся из describe индекса). При `--type TABLE` эти таблетки обрабатываются вместе с таблетками самой таблицы. Поток изменений на индексе лежит ещё глубже: `{таблица}/{индекс}/indexImplTable/{changefeed}/streamImpl`. При `--type PQ` он попадает в обработку по тому же префиксу пути, что и обычный CDC. Локальные индексы (bloom, min/max) отдельных таблеток не имеют.

Состав можно сузить префиксом пути. Префикс сравнивается по границе каталога: `/Root/database/orders` попадает в `/Root/database/orders` и в `/Root/database/orders/topic`, но не в `/Root/database/orders_old`. Относительный префикс дополняется путём базы. Фильтр по типу и префиксу один и тот же для остановки и запуска.

Операция задаётся `--action`:

| `--action` | Запрос Hive | Результат |
| --- | --- | --- |
| `stop` (по умолчанию) | `page=StopTablet` | Таблетка остаётся остановленной |
| `start` (синоним `resume`) | `page=ResumeTablet` | Hive снова загружает таблетку |

Оба запроса — `POST /tablets/app`. Идентификатор Hive читается из описания базы (`ProcessingParams.Hive`, иначе `SharedHive`); его можно задать явно через `--hive-id`. Это первое описание выполняется один раз: если оно не удалось, обычно неверен `--viewer-url`.

Обрыв или ошибка соединения при обходе схемы и при чтении состава таблеток повторяются до `--retries` раз (по умолчанию 5). Пауза перед повтором — 1 секунда, затем 2, 3 и так далее. Ошибка «доступ запрещён» не повторяется ни на этих запросах, ни при остановке и запуске таблеток.

Аутентификация такая же, как у остальных скриптов: `--auth Login` и токен в `~/.ydb/token`.

В stdout — по строке на таблетку: путь, id, роль, номера партиций, результат (`stopped`, `started`, `already-stopped`, `already-running`). Прогресс и итог — в stderr. Код выхода `2`, если каталог не удалось обойти, describe завершился с ошибкой или операцию над таблеткой не удалось выполнить.

```bash
# Остановить все топики базы
./manage_tablets.py --viewer-url https://ycydb-s1:8765 --auth Login \
  /Root/database

# Остановить только объекты под префиксом пути
./manage_tablets.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --path-prefix /Root/database/orders /Root/database

# Запустить те же топики
./manage_tablets.py --action start --viewer-url https://ycydb-s1:8765 --auth Login \
  --path-prefix /Root/database/orders /Root/database

# Показать цели, не выполняя операцию
./manage_tablets.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --path-prefix /Root/database/orders --dry-run /Root/database

# Даташарды таблиц и таблиц реализации вторичных индексов
./manage_tablets.py --viewer-url https://ycydb-s1:8765 --auth Login \
  --type TABLE --path-prefix schema1 --dry-run /Root/database
```

Другие значения `--type`: `TOPIC`, `PERS_QUEUE_GROUP`, `TABLE`, `COLUMN_TABLE`, `COLUMN_STORE`. Несколько видов перечисляются через запятую.

## Путь и тип объекта по TabletID

Скрипт `tablet_object.py` по идентификатору таблетки печатает полный путь схемного объекта и его тип. Hive хранит локальный path id объекта в поле `ObjectId`, а идентификатор SchemeShard — в `TabletOwner.Owner`. Скрипт читает эту запись через `/viewer/json/hiveinfo` и описывает объект по `path_id`.

Тип — схемный: `TABLE`, `TOPIC`, `COLUMN_TABLE`, `COLUMN_STORE`, `CDC_STREAM` и другие. Группа PersQueue, в том числе служебный топик CDC `{таблица}/{changefeed}/streamImpl`, печатается как `TOPIC`. Таблетка без схемного объекта (например, сам Hive) завершается ошибкой с типом таблетки в тексте.

Идентификатор Hive берётся из описания базы одним запросом, без повторов. Обрыв соединения при чтении Hive и описании объекта повторяется до `--retries` раз. Ошибка «доступ запрещён» не повторяется. Запрос describe по `path_id` требует права мониторинга.

В stdout — по строке на таблетку: `tablet_id`, путь и тип через табуляцию. Код выхода `2`, если хотя бы одну таблетку не удалось разрешить.

```bash
./tablet_object.py --viewer-url https://ycydb-s1:8765 --auth Login \
  /Root/database 72075186224123090

./tablet_object.py --viewer-url https://ycydb-s1:8765 --auth Login \
  /Root/database 72075186224123090 72075186224123091
```

## Незавершённые схемные операции

Скрипт `scheme_operations.py` выводит незавершённые транзакции SchemeShard выбранной базы. Список читается со страницы таблетки SchemeShard `Page=TxList` (это `TxInFlight`: DDL, split, создание CDC и другие схемные операции, которые ещё выполняются). Каждая строка списка — отдельная подоперация.

Для каждой подоперации скрипт открывает `Page=TxInfo` и забирает пути всех схемных объектов, которые SchemeShard записал в состояние транзакции:

- `target` — объект, который операция изменяет;
- `source` — объект-источник (копирование, перенос и похожие операции);
- `cdc` — CDC-поток.

Путь получается со страницы `Page=PathInfo`. Поле без path id в вывод не попадает. Если у подоперации несколько объектов, в stdout будет несколько строк с одинаковыми `tx_id` и `part_id`.

Идентификатор SchemeShard берётся из описания базы (`ProcessingParams.SchemeShard`) одним запросом, без повторов. Его можно передать явно через `--schemeshard-id`. Обрыв соединения при чтении списка, состояния транзакций и путей повторяется до `--retries` раз. Ошибка «доступ запрещён» не повторяется. Страницы таблетки требуют права мониторинга DevUI.

В stdout поля разделены табуляцией: `tx_id`, `part_id`, `type`, `state`, `shards_in_progress`, `role`, `path`. Код выхода `2`, если список прочитан, но хотя бы одну транзакцию или путь получить не удалось.

```bash
./scheme_operations.py --viewer-url https://ycydb-s1:8765 --auth Login \
  /Root/database
```

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
