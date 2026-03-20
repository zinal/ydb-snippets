# Установка сервисов мониторинга

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
