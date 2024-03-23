#! /bin/sh

ydb yql -f stroppy-recreate.yql

ydb -p stroppy table query exec -t scan -q 'SELECT * FROM `stroppy/account`' --format json-unicode | ydb -p stroppy import file json -p stroppy/account2

ydb tools rename --item src=stroppy/account,dst=stroppy/account_bak
ydb tools rename --item src=stroppy/account2,dst=stroppy/account
