#! /bin/sh

if [ "tls"=="$2" ]; then

${HOME}/ydb/bin/ydb -e grpcs://"$1":2135 --ca-file YdbWork/tls/ca.crt \
  -d /Root --user root --no-password auth get-token -f >ydbd-token-file

else

${HOME}/ydb/bin/ydb -e grpc://"$1":2135 \
  -d /Root --user root --no-password auth get-token -f >ydbd-token-file

fi

# ydb -e grpc://ycydb-s1:2135 -d /Root --user root --no-password auth get-token -f >ydbd-token-file
# scp ydbd-token-file yc-user@ycydb-s1:.
