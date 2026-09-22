# Образцы данных таблиц

## Список таблиц и оценка числа строк

```bash
psql -f sample-data/list-tables.sql
```

## Выгрузка образцов

```bash
# По 100 строк из указанных таблиц (schema.table)
./sample-data/dump-samples.sh public.users public.orders

# Другой лимит / каталог
LIMIT=50 OUT_DIR=out/samples ./sample-data/dump-samples.sh app.events
```

Формат вывода — CSV с заголовком (`COPY ... TO STDOUT WITH CSV HEADER`) в `out/samples/`.

Для очень больших таблиц предпочтительнее `TABLESAMPLE` — см. `sample-random.sql` (шаблон под конкретную таблицу).

## Осторожно

- Не выгружайте PII/секреты в git.
- На primary с высокой нагрузкой большие `ORDER BY random()` / full scan могут быть дороги — используйте `TABLESAMPLE` или ключ/`LIMIT` по индексу.
