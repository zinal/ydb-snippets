#! /bin/bash

set -e
set -u

CDC_FORMAT="$1"
CDC_COMPRESSION="$2"

. ../s3cloud.env

cat >tmp-replication.sql <<EOF
CREATE ASYNC REPLICATION source_repl FOR replication AS replication
WITH (
    FORMAT = '${CDC_FORMAT}', COMPRESSION = '${CDC_COMPRESSION}',
    USER = 'pagosyan',
    PASSWORD_SECRET_PATH = 'source_password',
    CONSISTENCY_LEVEL = 'ROW',
    CONNECTION_STRING = 'grpcs://onprem-dp-demos-0.int.zonne:2135/?database=/terttu1/db1',
    CA_CERT = @@
-----BEGIN CERTIFICATE-----
MIIFETCCAvmgAwIBAgIUNkoYfNQrTHJyuOgkuI82MDjDVx0wDQYJKoZIhvcNAQEL
BQAwHzEMMAoGA1UECgwDWURCMQ8wDQYDVQQDDAZZREIgQ0EwHhcNMjYxMTAxMTYw
MDM0WhcNMzExMTA1MTYwMDM0WjAfMQwwCgYDVQQKDANZREIxDzANBgNVBAMMBllE
QiBDQTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAI0vurZoZRqTcWc/
nxVe8gF9OogCPbsylItaM2j0JX7Bn5rV4G13kFmOQ2bDr+f9w7EUgcKEf/S8lDO+
XSfCnrXKPvs065NU3U7sznkkzJzTxs8RYDaDFOhLgPOyEXbS9iAE0Gc2re3pLCQf
LPpLZX1Td/wXy2u8iVayeD5WzDM5HkCl8iW3xeQtDilsKiMECF4lD9+QMfO6vyvY
4Z3oZS1CqLeSUiQHe5iS8K8SLkQLYlMFb2js1Ugf7En+W8RNOSEfNHRnECRvJyBh
yxCHJhl87kyzlbK/iIK2BIvhHx3W/gu9NAHvCONgMresnv7HLTXm8aaCBtTAAqwJ
F25I9yhuUAa+8X2rePnQIsZm9dX55ZJ5lSQtK+bl9/Y/OpQFQ4+PAFIHewi6ImUT
QuQFa91QjNsfS33v0JaJMWNFAv6n0azh8Lc4UsVsnkW5L2+Z5DmioYYlazem4emX
AZjO9NDFMPKsLqVI7MvReK0/GhkYSNuPWtGABFr4pHwxBzvvCskCu4/YNXiVT40h
iMleV6N1rILN4KRe2GTWGW8suQRgBA3oZJ6GZ7NTAv0I9tvdR60ZTl3OQyDBw/Sl
aQzUTKRh0Ia5nQp5a6pqnL6PyMwf8+6KqohCWPJu+u28S4CIK8i1qlsnLrojJluS
lU1q+33FiPDajKmc/zMqAzI/wPVTAgMBAAGjRTBDMA4GA1UdDwEB/wQEAwIC5DAS
BgNVHRMBAf8ECDAGAQH/AgEBMB0GA1UdDgQWBBQ9NTAGK+pXHsk6pq+T/SQXZllp
EzANBgkqhkiG9w0BAQsFAAOCAgEAGZ0y+G1rI3zR6KCuA3quufk4Aqkzi+ZQ3wcA
5c/QfQJoXF08xM3q+KcAPKaCpltb53DfOnLjJDFPefL9hJsGFOX0/z2H0IKvQGGr
JhfbL8wgGJpMrRUkz2rgJkhhagKZZHBw/+c8ks1g173/fBv7+VC8Ta6YisKKzF0e
iKlU657JmDmU0pkzrkAfgCF6kmcSlt9/pPk8rHI+vIbQ7wr4e8Oc5J0IZXBz0B84
My0dP5tpBz0/V98pw6m2YN6cvgilQtTyfWmP6z47cnPlIzWd23t5a3NE/xa8EPOG
rVcuGi2mZb65or55dA/NQ+CnGGQ9rPqHneAC2lk7PaRAdq9xtTKGNhUSXKV/fWaI
FptHLFrRq3i+P2sxi0eY+5uDmoeuFc14+XIevNRBeEIyd5gAqk6/EBe6fGZmnbcZ
vXfEkjJbECEs/DpnK3XdVKEIwZqMW/nZOwn3yaCsNTZfPCtl7o5qiT5yoqh+eWTQ
+BYu+RzMxZ0NEhTR+y/qWdrqsErR7Sb7O2lI8lO7XGEjUK/W+MxW439nw51I8jEx
HOWCPFD0Yb7jdjZxDQBRFq7Wcva7i9wiZ/dJQWai3f3ukjsgPsiQvn8uZ64FO+6T
VIv+QP30RSyLCIdAjCvKxlEb8kav3p6wjy7lQK4bexcPNzSQ2Y4Z/m4M1Dv5+C+8
HAw+K9I=
-----END CERTIFICATE-----
    @@
);
EOF

ydb -p db2 sql -s 'ALTER ASYNC REPLICATION source_repl SET (state="DONE")' || true
sleep 5
ydb -p db2 sql -s 'DROP ASYNC REPLICATION source_repl CASCADE;' || true

ydb -p db1 scheme rmdir -rf replication || true
ydb -p db2 scheme rmdir -rf replication || true

# initiate import
ydb import s3 --s3-endpoint ${S3_ENDPOINT} \
  --bucket onprem-dp-demos-1  --item src=backup-replication-5m/,dst=replication/ \
  --index-population-mode Import --format proto-json-base64 >tmp-import.json

# wait for import
IMPORT_ID=`jq -r .id <tmp-import.json`
~/snippets/admin/wait-ydb-operation.sh db1 "${IMPORT_ID}"

# forget import
ydb operation forget "${IMPORT_ID}"

# preload data into memory
ydb -p db1 sql -f preload.sql --stats basic >results/stats-${CDC_FORMAT}-${CDC_COMPRESSION}.txt


if [ "${CDC_FORMAT}" == "NONE" ]; then
  echo "Пропускаем создания репликации - не требуется"
else
  # create async replication
  ydb -p db2 sql -f tmp-replication.sql
  # wait for complete sync
  ~/snippets/admin/wait-ydb-replication-initial-sync.sh db2 source_repl
fi

# run test
echo "Запуск теста: `date`"
ydb workload replication run --init-pause 60s --seconds 1800 --users 500 --pause 50ms --window 30 >results/${CDC_FORMAT}-${CDC_COMPRESSION}.txt 2>&1
echo "Завершение теста: `date`"

exit 0
