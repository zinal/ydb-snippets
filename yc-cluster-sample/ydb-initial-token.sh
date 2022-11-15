#! /bin/sh

${HOME}/ydb/bin/ydb -e grpc://"$1":2135 -d /Root --user root --no-password auth get-token -f >ydbd-token-file
# ydb -e grpc://ycydb-1:2135 -d /Root --user root --no-password yql -s 'ALTER USER root PASSWORD "passw0rd"'
