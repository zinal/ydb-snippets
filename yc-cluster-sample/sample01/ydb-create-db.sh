#! /bin/sh

LD_LIBRARY_PATH=/opt/ydb/lib
export LD_LIBRARY_PATH

if [ "tls"=="$2" ]; then

/opt/ydb/bin/ydbd -f ydbd-token-file --ca-file YdbWork/tls/ca.crt -s grpcs://`hostname -s`:2135 \
  admin database /Root/testdb create ssd:"$1"
echo "Database creation status: $?"

else

/opt/ydb/bin/ydbd -f ydbd-token-file \
  admin database /Root/testdb create ssd:"$1"
echo "Database creation status: $?"

fi
