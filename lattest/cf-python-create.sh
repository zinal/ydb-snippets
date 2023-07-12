#! /bin/sh

SA_NAME=ydb-sa1
CF_NAME=cf-lattest-py
CF_ZIP=cf-lattest-py.zip

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
  --source-path ${CF_ZIP}

YDB_ENDPOINT=grpcs://lb.etnqkl8mc5g1iefthnh5.ydb.mdb.yandexcloud.net:2135
YDB_DATABASE=/ru-central1/b1gfvslmokutuvt2g019/etnqkl8mc5g1iefthnh5

yc serverless function create --name=${CF_NAME}-dd

yc serverless function version create \
  --function-name=${CF_NAME}-dd \
  --runtime python39 \
  --entrypoint lattest.handler \
  --memory 128m \
  --execution-timeout 30s \
  --service-account-id ${SA_ID} \
  --environment YDB_ENDPOINT=${YDB_ENDPOINT},YDB_DATABASE=${YDB_DATABASE} \
  --source-path ${CF_ZIP}
