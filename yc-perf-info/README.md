# Статистика производительности виртуальных машин

## Сводка

Во всех случаях запускали `sysbench cpu run --threads=8 --time=7200`.

|Поколение|vCPU|EPS1|EPS2|EPS3|
|---------|----|----|----|----|
|standard-v2|8|6957.97|6905.94|6908.92|
|standard-v2|16|8447.67|8442.69|8496.63|
|standard-v3|8|9830.71|9744.98|9651.86|
|standard-v3|16|18841.70|18745.04|18924.40|


## standard-v2 (Intel Cascade Lake), 8 vCPU

run 1:

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

run 2:

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
    events per second:  6905.94

General statistics:
    total time:                          7200.0007s
    total number of events:              49722795

Latency (ms):
         min:                                    0.83
         avg:                                    1.16
         max:                                   25.30
         95th percentile:                        1.27
         sum:                             57587478.73

Threads fairness:
    events (avg/stddev):           6215349.3750/876.76
    execution time (avg/stddev):   7198.4348/0.08
```

run 3:

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
    events per second:  6908.92

General statistics:
    total time:                          7200.0010s
    total number of events:              49744275

Latency (ms):
         min:                                    1.02
         avg:                                    1.16
         max:                                   14.56
         95th percentile:                        1.27
         sum:                             57587999.71

Threads fairness:
    events (avg/stddev):           6218034.3750/1890.06
    execution time (avg/stddev):   7198.5000/0.08
```

## standard-v2 (Intel Cascade Lake), 16 vCPU

run 1:

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

run 2:

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
    events per second:  8442.69

General statistics:
    total time:                          7200.0008s
    total number of events:              60787392

Latency (ms):
         min:                                    0.83
         avg:                                    0.95
         max:                                    2.46
         95th percentile:                        1.03
         sum:                             57586656.00

Threads fairness:
    events (avg/stddev):           7598424.0000/3308.87
    execution time (avg/stddev):   7198.3320/0.08
```

run 3:

```
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 8
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  8496.63

General statistics:
    total time:                          7200.0008s
    total number of events:              61175763

Latency (ms):
         min:                                    0.83
         avg:                                    0.94
         max:                                    1.77
         95th percentile:                        1.03
         sum:                             57586703.81

Threads fairness:
    events (avg/stddev):           7646970.3750/3602.63
    execution time (avg/stddev):   7198.3380/0.08
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

run 3:

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
    events per second:  9651.86

General statistics:
    total time:                          7200.0011s
    total number of events:              69493415

Latency (ms):
         min:                                    0.40
         avg:                                    0.83
         max:                                   18.85
         95th percentile:                        0.87
         sum:                             57581949.46

Threads fairness:
    events (avg/stddev):           8686676.8750/123.82
    execution time (avg/stddev):   7197.7437/0.04
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

run 3:

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
    events per second: 18924.40

General statistics:
    total time:                          7200.0004s
    total number of events:              136255745

Latency (ms):
         min:                                    0.36
         avg:                                    0.42
         max:                                    2.41
         95th percentile:                        0.45
         sum:                             57576417.58

Threads fairness:
    events (avg/stddev):           17031968.1250/4309.49
    execution time (avg/stddev):   7197.0522/0.03
```
