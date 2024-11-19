# YDB Insert5K - прогоны

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

### 5 потоков, 10 минут

Включен режим интегрированного COMMIT (флажком на последнем операторе вставки).

```
2024-11-05 08:27:56 INFO  Main:356 - Total 51 transactions, including 0 failures.
2024-11-05 08:27:56 INFO  Main:357 - Transaction retries: 14 total, average rate 27.45%
2024-11-05 08:27:56 INFO  Main:359 - Average success time, msec: 30013 (including retries)
2024-11-05 08:27:56 INFO  Main:361 - Average failure time, msec: 0 (including retries)
2024-11-05 08:27:56 INFO  Main:371 - *** table-a statistics
2024-11-05 08:27:56 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-05 08:27:56 INFO  Main:373 - *** 	Timing: 9878 max, 3729 avg (msec)
2024-11-05 08:27:56 INFO  Main:371 - *** table-b statistics
2024-11-05 08:27:56 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-05 08:27:56 INFO  Main:373 - *** 	Timing: 6796 max, 2427 avg (msec)
2024-11-05 08:27:56 INFO  Main:371 - *** table-c statistics
2024-11-05 08:27:56 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-05 08:27:56 INFO  Main:373 - *** 	Timing: 7009 max, 2048 avg (msec)
2024-11-05 08:27:56 INFO  Main:371 - *** table-d statistics
2024-11-05 08:27:56 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-05 08:27:56 INFO  Main:373 - *** 	Timing: 8412 max, 2698 avg (msec)
2024-11-05 08:27:56 INFO  Main:371 - *** table-e statistics
2024-11-05 08:27:56 INFO  Main:372 - *** 	Counts: 65 total, 14 failed
2024-11-05 08:27:56 INFO  Main:373 - *** 	Timing: 26604 max, 12244 avg (msec)
```

Виды сообщений об ошибках, вызывающих повторы транзакций:

```
2024-11-05 08:24:26 WARN  Main:263 - Task W1TrwnzNTlazWQIQ9sLNhw preliminarily failed on step TABLE:table-e with Status{code = UNAVAILABLE(code=400050), issues = [#2005 Kikimr cluster or one of its subsystems was unavailable. (S_ERROR)
  Could not deliver program to shard 72075186224041693 (S_ERROR)]}

2024-11-05 08:24:31 WARN  Main:263 - Task I23m4y8ERVij1MmF4B7g_g preliminarily failed on step TABLE:table-e with Status{code = ABORTED(code=400040), issues = [#2001 Transaction locks invalidated. Table: /cluster1/testdb/example-insert5k/table-a (S_ERROR)]}
```

Все ошибки выявляются на последнем операторе (в момент COMMIT).

## Запуски на 24.3.9.yasubd.2

### 5 потоков, 5 минут, запуск 1

Непустые таблицы, после апгрейда (т.е. после рестарта, кеши пустые).

Нет повторов (таблетки не ездят? похоже, дело в равномерном распределении по узлам после рестарта)

```
2024-11-07 16:11:01 INFO  Main:356 - Total 64 transactions, including 0 failures.
2024-11-07 16:11:01 INFO  Main:357 - Transaction retries: 0 total, average rate 0.00%
2024-11-07 16:11:01 INFO  Main:359 - Average success time, msec: 23369 (including retries)
2024-11-07 16:11:01 INFO  Main:361 - Average failure time, msec: 0 (including retries)
2024-11-07 16:11:01 INFO  Main:371 - *** table-a statistics
2024-11-07 16:11:01 INFO  Main:372 - *** 	Counts: 64 total, 0 failed
2024-11-07 16:11:01 INFO  Main:373 - *** 	Timing: 9708 max, 4884 avg (msec)
2024-11-07 16:11:01 INFO  Main:371 - *** table-b statistics
2024-11-07 16:11:01 INFO  Main:372 - *** 	Counts: 64 total, 0 failed
2024-11-07 16:11:01 INFO  Main:373 - *** 	Timing: 7882 max, 2769 avg (msec)
2024-11-07 16:11:01 INFO  Main:371 - *** table-c statistics
2024-11-07 16:11:01 INFO  Main:372 - *** 	Counts: 64 total, 0 failed
2024-11-07 16:11:01 INFO  Main:373 - *** 	Timing: 6283 max, 1665 avg (msec)
2024-11-07 16:11:01 INFO  Main:371 - *** table-d statistics
2024-11-07 16:11:01 INFO  Main:372 - *** 	Counts: 64 total, 0 failed
2024-11-07 16:11:01 INFO  Main:373 - *** 	Timing: 6314 max, 2607 avg (msec)
2024-11-07 16:11:01 INFO  Main:371 - *** table-e statistics
2024-11-07 16:11:01 INFO  Main:372 - *** 	Counts: 64 total, 0 failed
2024-11-07 16:11:01 INFO  Main:373 - *** 	Timing: 25456 max, 11438 avg (msec)
```

### 5 потоков, 5 минут, запуск 2

На пустых таблицах.

На старте - ездили таблетки, сколько-то вызванных этим ошибок (неравномерное распределение по узлам?).

```
2024-11-07 16:29:21 INFO  Main:356 - Total 49 transactions, including 3 failures.
2024-11-07 16:29:21 INFO  Main:357 - Transaction retries: 23 total, average rate 46.94%
2024-11-07 16:29:21 INFO  Main:359 - Average success time, msec: 30556 (including retries)
2024-11-07 16:29:21 INFO  Main:361 - Average failure time, msec: 2410 (including retries)
2024-11-07 16:29:21 INFO  Main:371 - *** table-a statistics
2024-11-07 16:29:21 INFO  Main:372 - *** 	Counts: 72 total, 3 failed
2024-11-07 16:29:21 INFO  Main:373 - *** 	Timing: 9667 max, 3544 avg (msec)
2024-11-07 16:29:21 INFO  Main:371 - *** table-b statistics
2024-11-07 16:29:21 INFO  Main:372 - *** 	Counts: 69 total, 0 failed
2024-11-07 16:29:21 INFO  Main:373 - *** 	Timing: 6212 max, 2482 avg (msec)
2024-11-07 16:29:21 INFO  Main:371 - *** table-c statistics
2024-11-07 16:29:21 INFO  Main:372 - *** 	Counts: 69 total, 0 failed
2024-11-07 16:29:21 INFO  Main:373 - *** 	Timing: 5425 max, 1542 avg (msec)
2024-11-07 16:29:21 INFO  Main:371 - *** table-d statistics
2024-11-07 16:29:21 INFO  Main:372 - *** 	Counts: 69 total, 0 failed
2024-11-07 16:29:21 INFO  Main:373 - *** 	Timing: 7151 max, 2386 avg (msec)
2024-11-07 16:29:21 INFO  Main:371 - *** table-e statistics
2024-11-07 16:29:21 INFO  Main:372 - *** 	Counts: 69 total, 23 failed
2024-11-07 16:29:21 INFO  Main:373 - *** 	Timing: 31378 max, 11377 avg (msec)
```


### 5 потоков, 5 минут, запуск 3

На таблицах от запуска 2, без рестарта (кеши заполнены).

Один ABORTED/TLI в середине, на средние тайминги не повлиял (по сравнению с запуском 1).

```
2024-11-07 16:36:13 INFO  Main:356 - Total 64 transactions, including 0 failures.
2024-11-07 16:36:13 INFO  Main:357 - Transaction retries: 1 total, average rate 1.56%
2024-11-07 16:36:13 INFO  Main:359 - Average success time, msec: 23475 (including retries)
2024-11-07 16:36:13 INFO  Main:361 - Average failure time, msec: 0 (including retries)
2024-11-07 16:36:13 INFO  Main:371 - *** table-a statistics
2024-11-07 16:36:13 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-07 16:36:13 INFO  Main:373 - *** 	Timing: 10827 max, 4324 avg (msec)
2024-11-07 16:36:13 INFO  Main:371 - *** table-b statistics
2024-11-07 16:36:13 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-07 16:36:13 INFO  Main:373 - *** 	Timing: 6993 max, 2587 avg (msec)
2024-11-07 16:36:13 INFO  Main:371 - *** table-c statistics
2024-11-07 16:36:13 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-07 16:36:13 INFO  Main:373 - *** 	Timing: 7927 max, 1971 avg (msec)
2024-11-07 16:36:13 INFO  Main:371 - *** table-d statistics
2024-11-07 16:36:13 INFO  Main:372 - *** 	Counts: 65 total, 0 failed
2024-11-07 16:36:13 INFO  Main:373 - *** 	Timing: 8005 max, 2377 avg (msec)
2024-11-07 16:36:13 INFO  Main:371 - *** table-e statistics
2024-11-07 16:36:13 INFO  Main:372 - *** 	Counts: 65 total, 1 failed
2024-11-07 16:36:13 INFO  Main:373 - *** 	Timing: 23295 max, 11847 avg (msec)
```

## Запуски на 24.3.9.yasubd.2 + волатильные транзакции

### 5 потоков, 5 минут, запуск 1

Не пустая база (осталась после запуска 3 без волатильных транзакций)

```
2024-11-07 17:26:08 INFO  Main:356 - Total 174 transactions, including 0 failures.
2024-11-07 17:26:08 INFO  Main:357 - Transaction retries: 0 total, average rate 0.00%
2024-11-07 17:26:08 INFO  Main:359 - Average success time, msec: 7109 (including retries)
2024-11-07 17:26:08 INFO  Main:361 - Average failure time, msec: 0 (including retries)
2024-11-07 17:26:08 INFO  Main:371 - *** table-a statistics
2024-11-07 17:26:08 INFO  Main:372 - *** 	Counts: 174 total, 0 failed
2024-11-07 17:26:08 INFO  Main:373 - *** 	Timing: 4828 max, 1789 avg (msec)
2024-11-07 17:26:08 INFO  Main:371 - *** table-b statistics
2024-11-07 17:26:08 INFO  Main:372 - *** 	Counts: 174 total, 0 failed
2024-11-07 17:26:08 INFO  Main:373 - *** 	Timing: 2874 max, 1090 avg (msec)
2024-11-07 17:26:08 INFO  Main:371 - *** table-c statistics
2024-11-07 17:26:08 INFO  Main:372 - *** 	Counts: 174 total, 0 failed
2024-11-07 17:26:08 INFO  Main:373 - *** 	Timing: 2511 max, 481 avg (msec)
2024-11-07 17:26:08 INFO  Main:371 - *** table-d statistics
2024-11-07 17:26:08 INFO  Main:372 - *** 	Counts: 174 total, 0 failed
2024-11-07 17:26:08 INFO  Main:373 - *** 	Timing: 3062 max, 1131 avg (msec)
2024-11-07 17:26:08 INFO  Main:371 - *** table-e statistics
2024-11-07 17:26:08 INFO  Main:372 - *** 	Counts: 174 total, 0 failed
2024-11-07 17:26:08 INFO  Main:373 - *** 	Timing: 11940 max, 2613 avg (msec)
```
