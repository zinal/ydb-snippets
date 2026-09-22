# Подключение `psql` к удалённому PostgreSQL (без TLS)

Параметры: хост, порт, имя БД, логин, пароль. TLS отключён (`sslmode=disable`).

Подставьте свои значения вместо плейсхолдеров:

| Параметр | Плейсхолдер | Пример |
|----------|-------------|--------|
| Хост | `HOST` | `db.example.com` или `10.0.1.20` |
| Порт | `PORT` | `5432` |
| База | `DBNAME` | `appdb` |
| Логин | `USER` | `appuser` |
| Пароль | `PASSWORD` | `secret` |

## Вариант 1: всё в одной командной строке

Пароль через переменную окружения (libpq не принимает пароль как `-p` — `-p` это порт):

```bash
PGPASSWORD='PASSWORD' psql \
  "host=HOST port=PORT dbname=DBNAME user=USER sslmode=disable"
```

Эквивалент через флаги:

```bash
PGPASSWORD='PASSWORD' psql \
  -h HOST \
  -p PORT \
  -U USER \
  -d DBNAME \
  --set=sslmode=disable
```

Надёжнее задать `sslmode` в URI/conninfo (см. ниже), потому что `--set` — это переменная `psql`, а не параметр libpq.

**Рекомендуемый однострочник (URI):**

```bash
psql "postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=disable"
```

Если в пароле есть спецсимволы (`@`, `:`, `/`, `%`, `#` и т.п.), их нужно URL-encode, либо используйте `PGPASSWORD` + conninfo без пароля в URI:

```bash
PGPASSWORD='PASSWORD' psql "postgresql://USER@HOST:PORT/DBNAME?sslmode=disable"
```

## Вариант 2: переменные окружения `PG*`

```bash
export PGHOST=HOST
export PGPORT=PORT
export PGUSER=USER
export PGDATABASE=DBNAME
export PGPASSWORD='PASSWORD'
export PGSSLMODE=disable

psql
# или сразу запрос:
psql -c 'SELECT current_database(), current_user, inet_server_addr(), inet_server_port();'
```

Для этого каталога удобно скопировать шаблон:

```bash
cp env.example env.local
# отредактировать env.local
source env.local
psql -c 'SELECT version();'
```

## Вариант 3: файл `~/.pgpass` (пароль не в истории shell)

Строка формата `host:port:database:user:password`:

```text
HOST:PORT:DBNAME:USER:PASSWORD
```

```bash
chmod 600 ~/.pgpass
psql "host=HOST port=PORT dbname=DBNAME user=USER sslmode=disable"
```

## Проверка, что TLS выключен

```bash
psql "host=HOST port=PORT dbname=DBNAME user=USER sslmode=disable" \
  -c "SELECT version(); SHOW ssl;"
```

При успешном подключении без TLS `SHOW ssl;` обычно возвращает `off` на стороне сессии сервера (если сервер не форсирует SSL). Если сервер требует SSL, соединение с `sslmode=disable` будет отклонено — тогда уже нужен другой режим (`require` / `verify-full` и т.д.).

## Частые ошибки

| Симптом | Что проверить |
|---------|----------------|
| `connection refused` | Хост/порт, firewall, `listen_addresses` на сервере |
| `no pg_hba.conf entry` | Правило в `pg_hba.conf` для вашего IP/`host` (не только `hostssl`) |
| `password authentication failed` | Логин/пароль, метод в `pg_hba.conf` (`scram-sha-256` / `md5`) |
| `SSL connection is required` | Сервер или `pg_hba` требуют TLS — без TLS не подключиться |
| Пароль виден в `ps` / history | Используйте `~/.pgpass` или `PGPASSWORD` без записи в историю (`read -s`) |

Интерактивный ввод пароля без `PGPASSWORD`:

```bash
psql "host=HOST port=PORT dbname=DBNAME user=USER sslmode=disable"
# Password for user USER:
```
