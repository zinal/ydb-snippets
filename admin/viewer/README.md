# Инструменты для автоматизации операций через Embedded UI

## Аутентификация

Для YDB со статической аутентификацией доступ из скриптов в Embedded UI требует наличия токена. Токен можно получить, зайдя в интерфейс Embedded UI и затем обратившись к следующему адресу: https://localhost:8766/viewer/json/whoami
Вместо `localhost:8766` должен быть указан корректный адрес доступа к Embedded UI.

Полученный токен необходимо поместить в файл `~/.ydb/token`

## Принудительная компактификация таблеток

```bash
mkdir ~/.ydb
vi ~/.ydb/token

# Table compaction
./table_full_compact.py --viewer-url https://ycydb-s1:8766 --auth Login --all /Domain0/tpcc/order_line
```
