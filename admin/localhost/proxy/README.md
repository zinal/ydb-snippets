# Squid с аутентификацией без кеша и журналов запросов

Примеры предназначены для Ubuntu 26.04 и настраивают обычный forward proxy:

- доступ разрешён только после Basic-аутентификации;
- разрешены HTTP на порту 80 и HTTPS `CONNECT` на порту 443;
- кеширование ответов отключено;
- запросы и операции объектного кеша не журналируются.

Basic-аутентификация сама по себе не шифрует пароль. Поэтому в каталоге есть
два варианта:

- `squid-http.conf` слушает только `127.0.0.1:3128` и предназначен для
  подключения через SSH-туннель или VPN;
- `squid-https.conf` слушает TLS-порт `3129`. Клиент должен поддерживать
  HTTPS-прокси.

TLS здесь защищает соединение между клиентом и Squid. `ssl_bump` не используется:
Squid не расшифровывает трафик до HTTPS-сайтов.

## Установка

```bash
sudo apt update
sudo apt install --no-install-recommends squid apache2-utils openssl ca-certificates
```

В пакете Ubuntu helper для NCSA-аутентификации находится по адресу
`/usr/lib/squid/basic_ncsa_auth`. Проверить путь можно командой:

```bash
dpkg -L squid | grep '/basic_ncsa_auth$'
```

## Создание пользователей

Первая команда создаёт файл паролей и интерактивно запрашивает пароль:

```bash
sudo htpasswd -c /etc/squid/passwd proxyuser
sudo chown root:proxy /etc/squid/passwd
sudo chmod 640 /etc/squid/passwd
```

Следующих пользователей добавляйте без `-c`, иначе существующий файл будет
перезаписан:

```bash
sudo htpasswd /etc/squid/passwd another-user
```

Удаление пользователя:

```bash
sudo htpasswd -D /etc/squid/passwd another-user
```

## Вариант 1: SSH-туннель

Этот вариант совместим с клиентами, которые умеют работать только с обычным
HTTP-прокси. Squid остаётся недоступен извне, а SSH шифрует пароль и трафик до
прокси-сервера.

Установите локальную конфигурацию:

```bash
sudo cp /etc/squid/squid.conf /etc/squid/squid.conf.bak
sudo install -o root -g root -m 0644 squid-http.conf /etc/squid/squid.conf
sudo squid -k parse
sudo systemctl restart squid
sudo systemctl enable squid
```

На клиенте откройте туннель:

```bash
ssh -N -L 3128:127.0.0.1:3128 user@proxy.example.com
```

В другом терминале клиента проверьте прокси. Если указать только имя
пользователя, `curl` запросит пароль интерактивно и не оставит его в истории
команд:

```bash
curl --proxy http://127.0.0.1:3128 \
  --proxy-user proxyuser \
  https://example.com/
```

## Вариант 2: HTTPS-прокси

### Сертификат

Предпочтителен сертификат от публичного или корпоративного CA. Его имя должно
совпадать с DNS-именем прокси. Сертификат и ключ установите в ожидаемые примером
пути:

```bash
sudo install -d -o root -g proxy -m 0750 /etc/squid/tls
sudo install -o root -g proxy -m 0640 fullchain.pem /etc/squid/tls/proxy.crt
sudo install -o root -g proxy -m 0640 privkey.pem /etc/squid/tls/proxy.key
```

Для закрытого стенда можно выпустить самоподписанный сертификат. Значение
`PROXY_HOST` должно разрешаться на клиентах:

```bash
PROXY_HOST=proxy.example.com

sudo install -d -o root -g proxy -m 0750 /etc/squid/tls
sudo openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -days 365 \
  -keyout /etc/squid/tls/proxy.key \
  -out /etc/squid/tls/proxy.crt \
  -subj "/CN=${PROXY_HOST}" \
  -addext "subjectAltName=DNS:${PROXY_HOST}"
sudo chown root:proxy /etc/squid/tls/proxy.key /etc/squid/tls/proxy.crt
sudo chmod 0640 /etc/squid/tls/proxy.key /etc/squid/tls/proxy.crt
```

Самоподписанный сертификат защищает от пассивного перехвата только после того,
как клиент получил доверенную копию `proxy.crt` по отдельному защищённому каналу.
Не отключайте проверку сертификата опцией `-k`.

### Запуск

Проверьте, что пакет Squid собран с TLS:

```bash
squid -v | grep -E -- '--with-(gnutls|openssl)'
```

Установите конфигурацию:

```bash
sudo cp /etc/squid/squid.conf /etc/squid/squid.conf.bak
sudo install -o root -g root -m 0644 squid-https.conf /etc/squid/squid.conf
sudo squid -k parse
sudo systemctl restart squid
sudo systemctl enable squid
```

Разрешите порт только доверенным адресам. Например, с UFW:

```bash
sudo ufw allow from 203.0.113.10 to any port 3129 proto tcp
```

Замените тестовый адрес `203.0.113.10` реальным адресом клиента. Не открывайте
порт всему интернету только на основании наличия пароля.

Проверка с сертификатом доверенного CA:

```bash
curl --proxy https://proxy.example.com:3129 \
  --proxy-user proxyuser \
  https://example.com/
```

Для собственного CA или самоподписанного сертификата передайте клиенту
доверенную копию сертификата:

```bash
curl --proxy https://proxy.example.com:3129 \
  --proxy-cacert ./proxy.crt \
  --proxy-user proxyuser \
  https://example.com/
```

Не все браузеры и системные настройки прокси поддерживают TLS до самого прокси.
В таком случае используйте SSH-туннель, VPN либо клиент с поддержкой HTTPS-прокси.
Настройка Firefox для Android описана в следующем разделе.

## Firefox для Android

Для HTTPS-прокси с собственным центром сертификации на Android подходит Firefox
с официального сайта или из магазина приложений. Настройка хранится в браузере
и действует и в Wi-Fi, и в мобильной сети.

Поле прокси в настройках Wi-Fi задаёт обычный HTTP-прокси. TLS до Squid
включается PAC-файлом со схемой `HTTPS`.

### Центр сертификации

На телефон устанавливается сертификат центра сертификации, а не сертификат
самого прокси. Android принимает в это хранилище сертификат с расширением
`CA:TRUE`. Самоподписанный сертификат сервера из предыдущего раздела для этого
не подходит: выпустите отдельный CA и подпишите им сертификат прокси.

```bash
PROXY_HOST=proxy.example.com
sudo install -d -o root -g proxy -m 0750 /etc/squid/tls

sudo openssl req -x509 -newkey rsa:3072 -sha256 -nodes \
  -days 3650 \
  -keyout /etc/squid/tls/ca.key \
  -out /etc/squid/tls/ca.crt \
  -subj "/CN=Private proxy CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign"

sudo openssl req -newkey rsa:3072 -sha256 -nodes \
  -keyout /etc/squid/tls/proxy.key \
  -out /etc/squid/tls/proxy.csr \
  -subj "/CN=${PROXY_HOST}" \
  -addext "subjectAltName=DNS:${PROXY_HOST}" \
  -addext "extendedKeyUsage=serverAuth" \
  -addext "basicConstraints=CA:FALSE"

sudo openssl x509 -req -sha256 \
  -in /etc/squid/tls/proxy.csr \
  -CA /etc/squid/tls/ca.crt \
  -CAkey /etc/squid/tls/ca.key \
  -CAcreateserial \
  -out /etc/squid/tls/proxy.crt \
  -days 365 \
  -copy_extensions copy

sudo chown root:proxy /etc/squid/tls/ca.key /etc/squid/tls/ca.crt \
  /etc/squid/tls/proxy.key /etc/squid/tls/proxy.crt
sudo chmod 0640 /etc/squid/tls/ca.key /etc/squid/tls/ca.crt \
  /etc/squid/tls/proxy.key /etc/squid/tls/proxy.crt
sudo rm -f /etc/squid/tls/proxy.csr /etc/squid/tls/ca.srl
sudo systemctl restart squid
```

`proxy.crt` и `proxy.key` остаются в путях из `squid-https.conf`. На телефон
переносится только `ca.crt`, по уже доверенному каналу. Если сертификат прокси
выпускает корпоративный CA, на телефон устанавливается его корневой сертификат,
а команды выше не нужны.

### Доверие в Firefox

1. Откройте `ca.crt` на телефоне и установите его как центр сертификации.
   Android оставит уведомление о том, что сеть может проверяться.
2. В Firefox откройте **Настройки → О Firefox**, семь раз нажмите логотип и в
   **Secret Settings** включите **Use third party CA certificates**. Полностью
   закройте Firefox и откройте его снова.
3. Пока прокси в Firefox выключен, откройте `https://proxy.example.com:3129/`.
   Имя в адресе должно совпадать с сертификатом. Предупреждения о сертификате
   быть не должно: Squid может ответить ошибкой, но само TLS-соединение уже
   доверено.

### PAC-файл

Опубликуйте файл по HTTPS-адресу, который Firefox открывает напрямую. Для этого
адреса нужен сертификат, который Firefox уже доверяет. Загрузка PAC не идёт
через Squid.

```javascript
function FindProxyForURL(url, host) {
  return "HTTPS proxy.example.com:3129";
}
```

В стабильном Firefox откройте `chrome://geckoview/content/config.xhtml`. В Beta
и Nightly достаточно `about:config`. Установите:

| Параметр | Значение |
| --- | --- |
| `network.proxy.type` | `2` |
| `network.proxy.autoconfig_url` | HTTPS-адрес PAC-файла |
| `network.proxy.proxy_over_tls` | `true` |
| `network.proxy.use_direct_on_fail` | `false` |

При первом запросе Firefox спросит имя и пароль прокси. Пароль передаётся
внутри TLS-соединения с Squid. Значение `network.proxy.use_direct_on_fail`
оставляет трафик на прокси, если соединение с ним не установилось.

## Проверка настроек

Состояние сервиса и ошибки конфигурации:

```bash
systemctl status squid
journalctl -u squid --since today
```

`access_log none` отключает журнал HTTP-запросов. `cache_log /dev/null` отключает
административный файловый журнал Squid, но сообщения запуска и ошибки сервиса
остаются в systemd journal. Это не журнал посещённых URL.

В примерах нет директивы `cache_dir`, поэтому дисковое хранилище не создаётся.
Дополнительная директива `cache deny all` запрещает сохранение ответов также в
объектном кеше памяти. Буферы, необходимые для передачи текущего ответа, при этом
остаются.

После обновления конфигурации всегда выполняйте:

```bash
sudo squid -k parse
sudo systemctl reload squid
```
