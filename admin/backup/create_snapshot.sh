#!/bin/bash
# Скрипт согласованно копирует все таблицы и представления
# из корня базы данных или указанной схемы в другую указанную схему.

set -e
set -u

SOURCE_SCHEMA=""
TARGET_SCHEMA="g2_copy1"
YDB_CLI="ydb -e grpc://somehost.net:2135 -d /Root/testdb --user root1 --no-password"

${YDB_CLI} scheme mkdir ${TARGET_SCHEMA}

OBJECTS_FILE=work_objects.tmp
${YDB_CLI} scheme ls ${SOURCE_SCHEMA} -l --format json >${OBJECTS_FILE}

DB_TABLES_FILE=work_tables.tmp
cat ${OBJECTS_FILE} | jq -r 'sort_by(.size) | .[] | select(.type == "table") | .path' > ${DB_TABLES_FILE}

DB_VIEWS_FILE=work_views.tmp
cat ${OBJECTS_FILE} | jq -r '.[] | select(.type == "view") | .path' > ${DB_VIEWS_FILE}

tables_list=()
while IFS= read -r line; do
    if [[ $line != .sys* ]] && [[ $line != .metadata* ]] && [[ $line != backup* ]]; then
        tables_list+=($line)
    fi
done < ${DB_TABLES_FILE}

tools_copy_args=""
for table in ${tables_list[@]}; do
    if [ -z "${SOURCE_SCHEMA}" ]; then
        tools_copy_args="$tools_copy_args --item d=${TARGET_SCHEMA}/${table},s=${table}"
    else
        tools_copy_args="$tools_copy_args --item d=${TARGET_SCHEMA}/${table},s=${SOURCE_SCHEMA}/${table}"
    fi
done

echo "Copying tables to ${TARGET_SCHEMA}..."
${YDB_CLI} tools copy $tools_copy_args

cat ${DB_VIEWS_FILE} | while read VIEW; do
  rm -rf work_view_dir.tmp
  mkdir -p work_view_dir.tmp
  VIEW_PATH="${SOURCE_SCHEMA}/${VIEW}"
  if [ -z "${SOURCE_SCHEMA}" ]; then
    VIEW_PATH="${VIEW}"
  fi
  echo "Copying view ${VIEW_PATH} to ${TARGET_SCHEMA}/${VIEW}..."
  ${YDB_CLI} tools dump -p "${VIEW_PATH}" -o work_view_dir.tmp
  FN=work_view_dir.tmp/${VIEW}/create_view.sql
  if [ -f "${FN}" ]; then
    SRC=`head -n1 ${FN} | sed -n 's|.*backup root: "\(.*\)"|\1|p'`
    DB=`dirname ${SRC}`
    DST="${DB}/${TARGET_SCHEMA}"
    cat "${FN}" | sed "s|${SRC}/|${DST}/|"   \
      | sed "s|\"${SRC}\"|\"${DST}\"|"       \
      | sed "s|'${SRC}'|'${DST}'|" >${FN}.new
    mv ${FN}.new ${FN}
    set +e
    ${YDB_CLI} tools restore -p "${TARGET_SCHEMA}" -i work_view_dir.tmp
    set -e
  fi
  rm -rf work_view_dir.tmp
done