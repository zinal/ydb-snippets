#! /bin/sh

set -e
set +u

if [ "tls"=="$2" ]; then

   if [ -z "$3" ]; then

${HOME}/ydb/bin/ydb -e grpcs://"$1":2135 --ca-file YdbWork/tls/ca.crt \
  -d /Root --user root --no-password auth get-token -f >ydbd-token-file

   else

echo "$3" > .tmp-password
${HOME}/ydb/bin/ydb -e grpcs://"$1":2135 --ca-file YdbWork/tls/ca.crt \
  -d /Root --user root --password-file .tmp-password auth get-token -f >ydbd-token-file

   fi

else

${HOME}/ydb/bin/ydb -e grpc://"$1":2135 \
  -d /Root --user root --no-password auth get-token -f >ydbd-token-file

fi

# ydb -e grpc://ycydb-s1:2135 -d /Root --user root --no-password auth get-token -f >ydbd-token-file
# scp ydbd-token-file yc-user@ycydb-s1:.
