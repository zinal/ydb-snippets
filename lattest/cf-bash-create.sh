#! /bin/sh

SA_NAME=ydb-sa1
CF_NAME=cf-bash
CF_ZIP=cf-bash.zip

rm -f ${CF_ZIP}
zip -9 ${CF_ZIP} checkhost.sh
trap "rm -f ${CF_ZIP}" EXIT

SA_ID=`yc iam service-account get ${SA_NAME} | grep -E '^id: ' | (read x y && echo $y)`

YDB_HOST=lb.etn8j0e78ai4sb62tn32.ydb.mdb.yandexcloud.net

yc serverless function create --name=${CF_NAME}

yc serverless function version create \
  --function-name=${CF_NAME} \
  --runtime bash \
  --entrypoint checkhost.sh \
  --memory 128m \
  --execution-timeout 30s \
  --service-account-id ${SA_ID} \
  --environment YDB_HOST=${YDB_HOST} \
  --source-path ${CF_ZIP}
