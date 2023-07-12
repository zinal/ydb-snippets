#! /bin/sh

cat >requirements.txt <<EOF
ydb
yandexcloud
EOF
trap 'rm -f requirements.txt' EXIT

rm -f cf-lattest-py.zip
zip -9 cf-lattest-py.zip requirements.txt lattest.py
