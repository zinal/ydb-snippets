#! /bin/sh

ydb yql -s 'CREATE USER stroppy PASSWORD "passw0rd"'
ydb yql -s 'ALTER GROUP ADMINS ADD USER stroppy'
