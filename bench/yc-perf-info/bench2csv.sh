#! /bin/sh

cd sysbench-out
ls *.txt | while read fn; do
    num=`cat "$fn" | grep "events per second: " | (read x y z c && echo $c)`
    xn=`echo "$fn" | sed -n 's|.*-\([sd][0-9]\)[.]\([0-9]*c\)[.]txt|\1,\2|p'`; 
    if [ ! -z "$xn" ]; then 
        echo "$xn,$num"
    fi;
done 
