# Установка YDB и сервисов мониторинга

## Серверная часть YDB

1. Подготовка диска

```bash
sudo parted -s /dev/vdb mklabel gpt
sudo parted -s /dev/vdb mkpart primary 1MiB 100%
sudo parted -s /dev/vdb name 1 ydb_data_1
sudo partprobe /dev/vdb
sudo dd if=/dev/zero of=/dev/disk/by-partlabel/ydb_data_1 bs=1M count=1
```

2. Создание пользователя и каталогов

```bash
sudo useradd kikimr
sudo usermod -a -G disk kikimr
sudo mkdir -pv /opt/kikimr/bin
sudo mkdir -pv /opt/kikimr/conf
```

3. Установка бинарников

```bash
tar xf ydb-server.tar.gz
sudo install -m 0755 ydbd /opt/kikimr/bin/ydbd
sudo install -m 0755 ydb  /opt/kikimr/bin/ydb
```

4. Установка настроечных файлов

```bash
sudo install -m 0640 ydbd-config-storage.yaml  /opt/kikimr/conf/config-storage.yaml
sudo install -m 0640 ydbd-config-database.yaml /opt/kikimr/conf/config-database.yaml
sudo chown -v kikimr:kikimr /opt/kikimr/conf/config-*
```

В настроечных файлах зашито имя хоста - поправить по мере надобности.

5. Скрипты и systemd-юниты

```bash
sudo install -m 0755 ydb-transparent-hugepages.sh /usr/local/bin/ydb-transparent-hugepages.sh
sudo install -m 0755 ydbd-reset-all.sh /usr/local/bin/ydbd-reset-all.sh
sudo install -m 0644 ydbd-storage.service /etc/systemd/system/ydbd-storage.service
sudo install -m 0644 ydbd-pgdata.service  /etc/systemd/system/ydbd-pgdata.service
sudo install -m 0644 ydb-transparent-hugepages.service /etc/systemd/system/ydb-transparent-hugepages.service
sudo systemctl daemon-reload
```

6. Запуск

```bash
sudo systemctl start ydb-transparent-hugepages
sudo /usr/local/bin/ydbd-reset-all.sh
```

7. Контроль статуса

```bash
sudo systemctl status ydbd-storage --no-pager
sudo systemctl status ydbd-pgdata --no-pager
```

## Node exporter

На всех рабочих хостах:

```bash
sudo apt-get -y install prometheus-node-exporter
```

## Mimir

Скачать пакеты:

```bash
wget https://github.com/grafana/mimir/releases/download/mimir-3.0.4/mimir-3.0.4_amd64.deb
wget https://github.com/grafana/mimir/releases/download/mimir-3.0.4/metaconvert_3.0.4_amd64.deb
wget https://github.com/grafana/mimir/releases/download/mimir-3.0.4/mimirtool_3.0.4_amd64.deb
wget https://github.com/grafana/mimir/releases/download/mimir-3.0.4/query-tee_3.0.4_amd64.deb
```

Установить пакеты:

```bash
sudo dpkg -i $(pwd)/mimir-3.0.4_amd64.deb
sudo dpkg -i $(pwd)/metaconvert_3.0.4_amd64.deb
sudo dpkg -i $(pwd)/mimirtool_3.0.4_amd64.deb
sudo dpkg -i $(pwd)/query-tee_3.0.4_amd64.deb
```

Настроить конфигурационный файл:

```bash
sudo cp -v mimir-config.yml /etc/mimir/config.yml
sudo chown -v root:mimir /etc/mimir/config.yml
sudo chmod -v 0640 /etc/mimir/config.yml
```

Указать ключи доступа к S3, поправить имя бакета:

```bash
sudo vi /etc/mimir/config.yml
```

Создать рабочие каталоги:

```bash
sudo mkdir -pv /data/mimir/tsdb
sudo mkdir -pv /data/mimir/tsdb-sync
sudo mkdir -pv /data/mimir/compactor
sudo mkdir -pv /data/mimir/rules
sudo chown -R -v mimir:mimir /data/mimir
sudo chmod -v 0755 /data
```

Перезапустить и проверить состояние:

```bash
sudo systemctl restart mimir
sudo systemctl status mimir
```

## Alloy

```bash
wget https://github.com/grafana/alloy/releases/download/v1.14.1/alloy-1.14.1-1.amd64.deb
```

```bash
sudo dpkg -i $(pwd)/alloy-1.14.1-1.amd64.deb
```

```bash
sudo vi /etc/alloy/prometheus-config.yml
sudo vi /etc/alloy/node-exporter.yml
sudo vi /etc/alloy/ydbd-storage.yml
sudo vi /etc/alloy/ydbd-database-ydb.yml
sudo vi /etc/default/alloy
# CONFIG_FILE="/etc/alloy/prometheus-config.yml"
# CUSTOM_ARGS="--config.format=prometheus"
```

```bash
sudo systemctl enable alloy
sudo systemctl start alloy
sudo systemctl status alloy
```

## Grafana

```bash
sudo apt-get install -y adduser libfontconfig1 musl
wget https://dl.grafana.com/grafana/release/12.4.1/grafana_12.4.1_22846628243_linux_amd64.deb
sudo dpkg -i grafana_12.4.1_22846628243_linux_amd64.deb
```

## Tempo

```bash
wget https://github.com/grafana/tempo/releases/download/v2.10.3/tempo_2.10.3_linux_amd64.deb
sudo dpkg -i tempo_2.10.3_linux_amd64.deb
sudo cp -v tempo-config.yml /etc/tempo/config.yml
chown -v tempo /etc/tempo/config.yml
chmod -v 0600 /etc/tempo/config.yml

sudo mkdir -pv /data/tempo/blocks
sudo mkdir -pv /data/tempo/generator/wal
sudo mkdir -pv /data/tempo/wal/blocks
sudo chown -Rv tempo /data/tempo
sudo chmod -v 0660 /data/tempo

```