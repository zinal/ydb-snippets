#! /bin/bash

mkdir -pv results
./iteration.sh BINARY NONE >results/log-BINARY-NONE.txt 2>&1
./iteration.sh BINARY ZSTD >results/log-BINARY-ZSTD.txt 2>&1
./iteration.sh JSON NONE >results/log-JSON-NONE.txt 2>&1
./iteration.sh JSON ZSTD >results/log-JSON-ZSTD.txt 2>&1
./iteration.sh NONE NONE >results/log-NONE-NONE.txt 2>&1
