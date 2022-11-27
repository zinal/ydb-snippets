#! /bin/sh

sysbench cpu run --threads=8 --time=7200 >sysbench.out.txt 2>&1
