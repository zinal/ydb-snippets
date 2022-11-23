#! /bin/sh

ydb -e grpc://ycydb-16:2136 -d /Root/testdb --user root --no-password yql -s 'ALTER USER root PASSWORD "passw0rd"'
ydb -e grpc://ycydb-16:2136 -d /Root/testdb --user root yql -s 'CREATE USER stroppy PASSWORD "passw0rd"'
ydb -e grpc://ycydb-16:2136 -d /Root/testdb --user root yql -s 'ALTER GROUP ADMINS ADD USER stroppy'
