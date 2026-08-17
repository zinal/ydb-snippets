# SQL-запросы для анализа состояния PostgreSQL

Запуск одного файла:

```bash
psql -v ON_ERROR_STOP=1 -f state/01-overview.sql
```

Пакетный прогон с сохранением в `out/state/`:

```bash
mkdir -p out/state
for f in state/*.sql; do
  psql -v ON_ERROR_STOP=1 -f "$f" | tee "out/state/$(basename "$f" .sql).txt"
done
```

| Файл | Содержание |
|------|------------|
| `01-overview.sql` | Версия, сессия, размеры БД, ключевые GUC |
| `02-extensions-schemas-roles.sql` | Расширения, схемы, роли |
| `03-sizes.sql` | Топ объектов/таблиц по размеру, vacuum/analyze |
| `04-activity.sql` | Сессии, активные запросы, долгие транзакции |
| `05-locks.sql` | Блокировки и граф блокирующих |
| `06-replication.sql` | Слоты и lag репликации |
