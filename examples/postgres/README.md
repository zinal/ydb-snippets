# PostgreSQL: анализ состояния, схема, образцы данных

Каталог для интерактивной фиксации рабочих команд `psql` / `pg_dump` при разборе чужой или своей БД PostgreSQL.

Структура:

| Каталог | Назначение |
|---------|------------|
| [`state/`](state/) | SQL для обзора состояния кластера/БД (версии, размеры, активность, блокировки) |
| [`schema/`](schema/) | Выгрузка DDL схемы (`pg_dump --schema-only` и вспомогательные запросы) |
| [`sample-data/`](sample-data/) | Выборочная выгрузка строк из таблиц |

Артефакты прогонов складываем в `out/` (каталог в `.gitignore`).

## Подключение

Задайте переменные (или скопируйте `env.example` → `env.local` и `source` его):

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=postgres
export PGDATABASE=mydb
# export PGPASSWORD=...   # или ~/.pgpass
# export PGSSLMODE=require
```

Проверка:

```bash
psql -c 'SELECT version();'
psql -c 'SELECT current_database(), current_user, inet_server_addr(), inet_server_port();'
```

## Типовой сценарий разбора

1. **Состояние** — прогнать запросы из `state/` (версия, расширения, размеры, активность, блокировки).
2. **Схема** — `schema/dump-schema.sh` → DDL в `out/schema/`.
3. **Образцы** — `sample-data/list-tables.sql`, затем `sample-data/dump-samples.sh` для нужных таблиц.

```bash
mkdir -p out/{state,schema,samples}

# 1. Состояние
for f in state/*.sql; do
  echo "=== $f ==="
  psql -v ON_ERROR_STOP=1 -f "$f" | tee "out/state/$(basename "$f" .sql).txt"
done

# 2. Схема
./schema/dump-schema.sh

# 3. Образцы (пример: public.orders, public.users)
./sample-data/dump-samples.sh public.orders public.users
```

## Замечания

- Команды намеренно разбиты на небольшие файлы — удобно править и дополнять по ходу сессии.
- Для больших таблиц в образцах используйте `LIMIT` / `TABLESAMPLE` (см. `sample-data/`).
- Не коммитьте `env.local`, пароли и содержимое `out/`.
