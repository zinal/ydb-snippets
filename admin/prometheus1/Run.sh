#! /bin/sh

nohup ./prometheus --config.file=prometheus-ydb.yml >Run.log 2>&1 </dev/null &
