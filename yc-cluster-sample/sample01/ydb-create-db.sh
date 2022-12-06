#! /bin/sh

LD_LIBRARY_PATH=/opt/ydb/lib
export LD_LIBRARY_PATH

/opt/ydb/bin/ydbd -f ydbd-token-file admin database /Root/testdb create ssd:8
echo "Database creation status: $?"
