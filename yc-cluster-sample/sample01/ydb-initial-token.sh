#! /bin/sh

${HOME}/ydb/bin/ydb -e grpc://"$1":2135 -d /Root --user root --no-password auth get-token -f >ydbd-token-file
# ydb -e grpc://ycydb-s1:2135 -d /Root --user root --no-password auth get-token -f >ydbd-token-file
# scp ydbd-token-file yc-user@ycydb-s1:.
