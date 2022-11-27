#! /bin/sh

sysbench cpu run --threads=16 --time=7200 >sysbench.out.txt 2>&1
