# Кластер YDB на 6 ВМ: раздельные узлы хранения и БД (Ansible, конфигурация V1)

Пример конфигурации для развёртывания кластера YDB по схеме «3+3» с помощью
коллекции playbook'ов
[ydb-platform/ydb-ansible](https://github.com/ydb-platform/ydb-ansible):

| Группа          | ВМ                                                     | Роль                          | vCPU |
| --------------- | ------------------------------------------------------ | ----------------------------- | ---- |
| `ydbd_static`   | `storage-a/b/c.rnd-ydb.example.com`                    | Static (storage) nodes        | 8    |
| `ydbd_dynamic`  | `database-a/b/c.rnd-ydb.example.com`                   | Dynamic (database `db1`) nodes| 16   |

Основные параметры:

- **Конфигурация V1** (`ydb_config_v2: false`).
- **Оффлайн-установка**: бинарный архив YDB берётся по фиксированному пути
  `/opt/ydb-dist/ydbd-server.tar.gz` (`ydb_archive`). Это путь **на управляющем
  хосте** (там, где запускается `ansible-playbook`); доставку архива на 6 ВМ
  обеспечивает сам Ansible.
- **Домен**: `/rnd-ydb`, **база**: `db1` (полный путь — `/rnd-ydb/db1`).
- **Топология хранения**: `mirror-3-dc` в сокращённом варианте (3 узла).
- **3 группы хранения** в БД (`ydb_database_groups: 3`).
- **Динамическая конфигурация БД**: настройки `memory_controller_config`
  применяются на уровне базы `/rnd-ydb/db1` через `selector_config`
  в `files/dynconfig.yaml`.

## Почему `initial_setup` НЕ ПОДХОДИТ

Официальная документация YDB описывает только «слитный» сценарий, когда на
каждой ВМ работают и storage-, и dynamic-узлы. Playbook
`ydb_platform.ydb.initial_setup` импортирует роли `ydbd_static` и `ydbd_dynamic`
с одним и тем же host-pattern (`ansible_play_hosts | default('ydb')`), а
значит обе будут выполнены на всех 6 ВМ — на узлах БД будет запущен
ydbd-storage и будут отформатированы их диски.

Для раздельной топологии используется набор granular playbook'ов из той же
коллекции, который умеет работать с подгруппами `ydbd_static` / `ydbd_dynamic`:

- `prepare_host` — выполняется на всех ВМ (group `ydb`);
- `binaries_all` — распаковка `ydb_archive` на всех ВМ;
- `install_static` — bootstrap кластера хранения **только** на `ydbd_static`
  (по умолчанию работает на всю группу `ydb`, поэтому ограничиваем флагом
  `-l ydbd_static`);
- `create_database` — автоматически использует группу `ydbd_static`;
- `install_dynamic` — автоматически использует группу `ydbd_dynamic`.

Готовый сценарий собран в [`deploy.sh`](./deploy.sh).

## Структура каталога

```
3x3/
├── README.md                       # этот файл
├── ansible.cfg                     # конфиг Ansible (inventory, vault, ssh)
├── ansible_vault_password_file     # пароль для расшифровки vault-файла
├── deploy.sh                       # сценарий развёртывания
├── inventory/
│   ├── 50-inventory.yaml           # хосты + переменные (см. ниже)
│   └── 99-inventory-vault.yaml     # пароль root (необходимо зашифровать!)
└── files/
    ├── config.yaml                 # статическая конфигурация V1 кластера
    └── dynconfig.yaml              # динамическая конфигурация (memory_controller_config)
```

## Подготовка

1. Установите Ansible 2.11–2.18 и коллекцию YDB:

   ```bash
   pip install 'ansible-core>=2.15,<2.19'
   ansible-galaxy collection install \
       git+https://github.com/ydb-platform/ydb-ansible.git,latest
   ```

2. Подготовьте 6 ВМ (Ubuntu / Debian / AlmaLinux / RHEL — см. список
   поддерживаемых ОС в [README ydb-ansible](https://github.com/ydb-platform/ydb-ansible)).
   Обеспечьте:
   - SSH-доступ под пользователем `ansible_user` с приватным ключом
     `ansible_ssh_private_key_file`;
   - passwordless sudo для этого пользователя;
   - Python ≥ 3.8.

   Архив YDB (`ydbd-server-<version>-linux-amd64.tar.gz`) скачайте со
   [страницы загрузок](https://ydb.tech/docs/ru/downloads) и положите
   на **управляющий хост** по пути из переменной `ydb_archive`
   (по умолчанию `/opt/ydb-dist/ydbd-server.tar.gz`). На целевые ВМ
   Ansible доставит его сам.

3. Откорректируйте `inventory/50-inventory.yaml` под Ваши реальные FQDN,
   SSH-доступ, дисковую раскладку (`ydb_disks`), часовой пояс и NTP.
   В минимальной правке нуждаются:
   - имена хостов (6 штук);
   - `ansible_user`, `ansible_ssh_private_key_file`;
   - `ydb_disks` (имена блочных устройств для PDisk);
   - `system_timezone`, `system_ntp_servers`.

4. Также замените все имена `storage-a/b/c.rnd-ydb.example.com` на реальные FQDN
   в файле `files/config.yaml` (секции `hosts:` и `blob_storage_config:`).

5. Откорректируйте `files/dynconfig.yaml`: значения `hard_limit_bytes`,
   `query_execution_limit_bytes` и пр. зависят от реального объёма RAM ВМ
   узлов БД. Приведённые величины ориентированы на 64 ГБ RAM.

6. Установите пароль `root` в vault-файле и зашифруйте его:

   ```bash
   # 1) задайте сильный пароль vault'а
   echo 'MyStrongVaultPassphrase' > ansible_vault_password_file
   chmod 600 ansible_vault_password_file

   # 2) задайте пароль root внутри 99-inventory-vault.yaml,
   #    после чего зашифруйте файл:
   ansible-vault encrypt inventory/99-inventory-vault.yaml
   ```

## Развёртывание

```bash
./deploy.sh
```

После успешного завершения проверьте состояние кластера:

- Embedded UI узла хранения: `https://storage-a.rnd-ydb.example.com:8765/monitoring/cluster/tenants`
- Embedded UI dynnode базы:  `https://database-a.rnd-ydb.example.com:8766/monitoring/cluster/tenants`

(если прямого доступа к портам нет — пробросьте SSH-туннель
`ssh -L 8765:localhost:8765 ...`).

## Подключение клиентом YDB CLI

```bash
ydb \
  -e grpcs://storage-a.rnd-ydb.example.com:2135 \
  -d /rnd-ydb/db1 \
  --ca-file files/TLS/certs/ca.crt \
  --user root \
  sql -s 'SELECT 1;'
```

Брокер на любом storage-узле (порт 2135) выполнит discovery и переключит
клиента на эндпоинты dynnode (порт 2136).

## Изменение настроек памяти БД (повторное применение dynconfig)

После правки `files/dynconfig.yaml` примените изменения:

```bash
ansible-playbook ydb_platform.ydb.update_dynconfig
```

Этот playbook применяет новый dynconfig и автоматически делает rolling restart
динамических узлов.

## Что важно помнить

- Переменная `ydb_archive` задаёт локальный путь к архиву на **управляющем
  хосте** (там, где запускается `ansible-playbook`). На целевые ВМ файл
  доставляет сам Ansible. Альтернатива — `ydb_version` (онлайн-режим,
  скачивание официального релиза по номеру версии).
- `ydb_brokers` — это ровно 3 имени узлов **хранения**. Динамические узлы
  используют этот список как `--node-broker grpcs://<host>:2135`.
- `ydb_database_groups: 3` — приемлемое значение для тестового кластера.
  Для production с дисками > 800 ГБ ориентируйтесь на ~84 % от общего числа
  PDisk при `mirror-3-dc` (см. документацию).
- Топология `mirror-3-dc` на 3 узлах допускает потерю **одного** узла без
  потери данных; промышленные кластеры обычно собирают на 9 узлах
  (по 3 на зону).
