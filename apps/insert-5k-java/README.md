# YDB Insert5K

Пример реализации интерактивной транзакции, выполняющей параллельную (в X потоков) вставку N порций данных по Q записей в N разных таблиц с использованием Query Service.

Для сборки и запуска требуется JDK 17 и Maven.

Параметры подключения к БД прописываются в `example1.xml`.

При успешном выполнении рабочие таблички и схема удаляются.

```bash
mvn clean package
ydb scheme rmdir -r example-insert5k
mvn exec:java
```

## Прогоны на 10k строк

Первоначальная конфигурация: ydbd 24.3.9.yasubd.1

```yaml
table_service_config:
  sql_version: 1
  index_auto_choose_mode: MAX_USED_PREFIX
  enable_kqp_data_query_stream_lookup: true
  resource_manager:
    kqp_pattern_cache_compiled_capacity_bytes: 524288000
    kqp_pattern_cache_capacity_bytes: 524288000

feature_flags:
  enable_views: true

resource_broker_config:
  queues:
  - name: queue_restore
    limit:
      cpu: 8
  - name: queue_backup
    limit:
      cpu: 8
```

### 1 поток, 5 минут

```
2024-11-05 05:53:37 INFO  Main:295 - Total 29 transactions, including 0 failures.
2024-11-05 05:53:37 INFO  Main:296 - Transaction retries: 0 total, average rate 0.00%
2024-11-05 05:53:37 INFO  Main:298 - Average success time, msec: 10193 (including retries)
2024-11-05 05:53:37 INFO  Main:300 - Average failure time, msec: 0 (including retries)
2024-11-05 05:53:37 INFO  Main:309 - *** COMMIT statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 6905 max, 6178 avg (msec)
2024-11-05 05:53:37 INFO  Main:309 - *** table-a statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 1894 max, 1505 avg (msec)
2024-11-05 05:53:37 INFO  Main:309 - *** table-b statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 1019 max, 908 avg (msec)
2024-11-05 05:53:37 INFO  Main:309 - *** table-c statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 664 max, 408 avg (msec)
2024-11-05 05:53:37 INFO  Main:309 - *** table-d statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 1033 max, 922 avg (msec)
2024-11-05 05:53:37 INFO  Main:309 - *** table-e statistics
2024-11-05 05:53:37 INFO  Main:310 - *** 	Counts: 29 total, 0 failed
2024-11-05 05:53:37 INFO  Main:311 - *** 	Timing: 391 max, 267 avg (msec)
```

### 2 потока, 5 минут

```
2024-11-05 06:00:15 INFO  Main:295 - Total 38 transactions, including 0 failures.
2024-11-05 06:00:15 INFO  Main:296 - Transaction retries: 5 total, average rate 13.16%
2024-11-05 06:00:15 INFO  Main:298 - Average success time, msec: 15670 (including retries)
2024-11-05 06:00:15 INFO  Main:300 - Average failure time, msec: 0 (including retries)
2024-11-05 06:00:15 INFO  Main:309 - *** COMMIT statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 5 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 11583 max, 7071 avg (msec)
2024-11-05 06:00:15 INFO  Main:309 - *** table-a statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 0 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 5406 max, 2521 avg (msec)
2024-11-05 06:00:15 INFO  Main:309 - *** table-b statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 0 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 3858 max, 1556 avg (msec)
2024-11-05 06:00:15 INFO  Main:309 - *** table-c statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 0 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 3283 max, 954 avg (msec)
2024-11-05 06:00:15 INFO  Main:309 - *** table-d statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 0 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 3272 max, 1223 avg (msec)
2024-11-05 06:00:15 INFO  Main:309 - *** table-e statistics
2024-11-05 06:00:15 INFO  Main:310 - *** 	Counts: 43 total, 0 failed
2024-11-05 06:00:15 INFO  Main:311 - *** 	Timing: 2779 max, 512 avg (msec)
```

Причина повторов - TLI (KIKIMR_LOCKS_INVALIDATED).

Полношардовых блокировок, судя по метрикам, нет.

### 5 потоков, 5 минут

```
2024-11-05 06:26:02 INFO  Main:306 - Total 29 transactions, including 0 failures.
2024-11-05 06:26:02 INFO  Main:307 - Transaction retries: 43 total, average rate 148.28%
2024-11-05 06:26:02 INFO  Main:309 - Average success time, msec: 53672 (including retries)
2024-11-05 06:26:02 INFO  Main:311 - Average failure time, msec: 0 (including retries)
2024-11-05 06:26:02 INFO  Main:320 - *** COMMIT statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 43 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 22900 max, 9933 avg (msec)
2024-11-05 06:26:02 INFO  Main:320 - *** table-a statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 0 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 10547 max, 3413 avg (msec)
2024-11-05 06:26:02 INFO  Main:320 - *** table-b statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 0 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 5658 max, 1949 avg (msec)
2024-11-05 06:26:02 INFO  Main:320 - *** table-c statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 0 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 4879 max, 1396 avg (msec)
2024-11-05 06:26:02 INFO  Main:320 - *** table-d statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 0 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 8022 max, 1903 avg (msec)
2024-11-05 06:26:02 INFO  Main:320 - *** table-e statistics
2024-11-05 06:26:02 INFO  Main:321 - *** 	Counts: 72 total, 0 failed
2024-11-05 06:26:02 INFO  Main:322 - *** 	Timing: 8317 max, 1127 avg (msec)
```

Причины повторов - TLI (KIKIMR_LOCKS_INVALIDATED) и UNAVAILABLE.

Ненулевая активность Hive по перевозу таблеток в момент исполнения транзакций. Судя по Hive UI, возит из-за неравномерного использования памяти:

```
Balancer	Runs	Moves	Last run	Last moves	Progress
Counter         0	0
CPU             0	0
Memory          715	715	2024-11-05T06:56:09.239762Z	1
Network         0	0
Emergency	0	0
Spread          0	0
Scatter         0	0
Manual          0	0
Storage         0	0
```

