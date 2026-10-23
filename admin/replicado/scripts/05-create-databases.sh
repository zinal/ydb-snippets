#! /bin/sh

./sw/ydbd --ca-file certs/ca.crt -s grpcs://localhost:2135 -f auth_token \
    admin database /Root/source create ssd:2
echo $?

./sw/ydbd --ca-file certs/ca.crt -s grpcs://localhost:2135 -f auth_token \
    admin database /Root/target create ssd:2
echo $?

