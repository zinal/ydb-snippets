#! /bin/sh

ydb yql -f stroppy-recreate.yql

ydb table query exec -t scan --tx-mode online-ro -q 'SELECT * FROM `stroppy/account`' --format json-unicode | ydb import file json -p stroppy/account2

ydb tools rename --item src=stroppy/account,dst=stroppy/account_bak
ydb tools rename --item src=stroppy/account2,dst=stroppy/account
