# Статистика производительности виртуальных машин

## Сводка

Во всех случаях запускали `sysbench cpu run --threads=8 --time=7200`.

|Поколение|vCPU|EPS1|EPS2|
|---------|----|----|----|
|standard-v2|8|6957.97||
|standard-v2|16|8447.67||
|standard-v3|8|9830.71||
|standard-v3|16|18841.70|18745.04|


## standard-v2 (Intel Cascade Lake), 8 vCPU

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

## standard-v2 (Intel Cascade Lake), 16 vCPU

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

## standard-v3 (Intel Ice Lake), 8 vCPU

run 1:

```
zinal@test-g3-8c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  9830.71

General statistics:
    total time:                          7200.0007s
    total number of events:              70781142

Latency (ms):
         min:                                    0.38
         avg:                                    0.81
         max:                                   32.73
         95th percentile:                        0.86
         sum:                             57581991.53

Threads fairness:
    events (avg/stddev):           8847642.7500/295.77
    execution time (avg/stddev):   7197.7489/0.02
```

run 2:

```
zinal@test-g3-8c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  9744.98

General statistics:
    total time:                          7200.0003s
    total number of events:              70163883

Latency (ms):
         min:                                    0.39
         avg:                                    0.82
         max:                                   24.54
         95th percentile:                        0.86
         sum:                             57582831.16

Threads fairness:
    events (avg/stddev):           8770485.3750/254.80
    execution time (avg/stddev):   7197.8539/0.02
```

## standard-v3 (Intel Ice Lake), 16 vCPU

run 1:

```
zinal@test-g3-16c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second: 18841.70

General statistics:
    total time:                          7200.0006s
    total number of events:              135660270

Latency (ms):
         min:                                    0.36
         avg:                                    0.42
         max:                                    1.88
         95th percentile:                        0.45
         sum:                             57576318.13

Threads fairness:
    events (avg/stddev):           16957533.7500/6557.84
    execution time (avg/stddev):   7197.0398/0.03
```

run 2:

```
zinal@test-g3-16c:~$ sysbench cpu run --threads=8 --time=7200
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second: 18745.04

General statistics:
    total time:                          7200.0006s
    total number of events:              134964348

Latency (ms):
         min:                                    0.36
         avg:                                    0.43
         max:                                    2.19
         95th percentile:                        0.45
         sum:                             57576104.39

Threads fairness:
    events (avg/stddev):           16870543.5000/3624.00
    execution time (avg/stddev):   7197.0130/0.04
```
