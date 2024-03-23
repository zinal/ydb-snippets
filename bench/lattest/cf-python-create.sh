#! /bin/sh

set -e
set -u

SA_NAME=ydb-sa1
CF_NAME=cf-lattest-py
CF_ZIP=cf-lattest-py.zip

cat >requirements.txt <<EOF
ydb
yandexcloud
EOF
trap 'rm -f requirements.txt' EXIT

rm -f ${CF_ZIP}
zip -9 ${CF_ZIP} requirements.txt lattest.py yandexca.cer
trap "rm -f ${CF_ZIP}" EXIT

SA_ID=`yc iam service-account get ${SA_NAME} | grep -E '^id: ' | (read x y && echo $y)`

YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
YDB_DATABASE=/ru-central1/b1gfvslmokutuvt2g019/etnuogblap3e7dok6tf5

yc serverless function create --name=${CF_NAME}-sl

yc serverless function version create \
  --function-name=${CF_NAME}-sl \
  --runtime python39 \
  --entrypoint lattest.handler \
  --memory 128m \
  --execution-timeout 30s \
  --service-account-id ${SA_ID} \
  --environment YDB_ENDPOINT=${YDB_ENDPOINT},YDB_DATABASE=${YDB_DATABASE} \
  --source-path ${CF_ZIP} --async

YDB_ENDPOINT=grpcs://lb.etn8j0e78ai4sb62tn32.ydb.mdb.yandexcloud.net:2135
YDB_DATABASE=/ru-central1/b1gfvslmokutuvt2g019/etn8j0e78ai4sb62tn32

yc serverless function create --name=${CF_NAME}-dd

yc serverless function version create \
  --function-name=${CF_NAME}-dd \
  --runtime python39 \
  --entrypoint lattest.handler \
  --memory 128m \
  --execution-timeout 30s \
  --service-account-id ${SA_ID} \
  --environment YDB_ENDPOINT=${YDB_ENDPOINT},YDB_DATABASE=${YDB_DATABASE},YDB_SSL_ROOT_CERTIFICATES_FILE=yandexca.cer \
  --source-path ${CF_ZIP} --async
