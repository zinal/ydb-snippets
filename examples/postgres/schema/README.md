# Выгрузка схемы (DDL)

## Быстрый дамп всей схемы текущей БД

```bash
./schema/dump-schema.sh
# → out/schema/<db>-schema.sql
# → out/schema/<db>-schema-globals.sql  (роли/tablespaces, если есть права)
```

Опции через переменные окружения:

| Переменная | По умолчанию | Смысл |
|------------|--------------|--------|
| `OUT_DIR` | `out/schema` | Куда писать файлы |
| `SCHEMAS` | *(все)* | Список схем через пробел (`public app`) |
| `EXCLUDE_SCHEMAS` | — | Исключить схемы |

Примеры:

```bash
SCHEMAS='public' ./schema/dump-schema.sh
EXCLUDE_SCHEMAS='pglogical tiger' ./schema/dump-schema.sh
```

## Точечные запросы (без pg_dump)

См. `inspect-objects.sql` — список таблиц/вьюх/индексов/функций и `pg_get_*def`.
