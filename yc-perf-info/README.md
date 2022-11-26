# Статистика производительности виртуальных машин

## Сводка

Во всех случаях запускали `sysbench cpu run --threads=8 --time=7200`.

|Поколение|vCPU|EPS|
|---------|----|---|
|G2|8|6957.97|
|G2|16|8447.67|


## G2 8C

```
zinal@test-g2-8c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  6957.97

General statistics:
    total time:                          7200.0010s
    total number of events:              50097423

Latency (ms):
         min:                                    0.82
         avg:                                    1.15
         max:                                   29.15
         95th percentile:                        1.27
         sum:                             57587862.97

Threads fairness:
    events (avg/stddev):           6262177.8750/675.80
    execution time (avg/stddev):   7198.4829/0.04
```

## G2 16C

```
zinal@test-g2-16c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  8447.67

General statistics:
    total time:                          7200.0010s
    total number of events:              60823243

Latency (ms):
         min:                                    0.83
         avg:                                    0.95
         max:                                    1.70
         95th percentile:                        1.03
         sum:                             57586567.14

Threads fairness:
    events (avg/stddev):           7602905.3750/3881.26
    execution time (avg/stddev):   7198.3209/0.08
```
