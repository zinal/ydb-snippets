# https://ydb.tech/ru/docs/maintenance/manual/adding_storage_groups

/opt/ydb/bin/ydbd -s grpc://ycydb-1:2136 --token-file ydbd-token-file admin bs config invoke --proto-file sp-query.txt >sp-query-result.txt

# Сделать на основе sp-query-result.txt файл sp-modify.txt, увеличив количество групп

/opt/ydb/bin/ydbd -s grpc://ycydb-1:2136 --token-file ydbd-token-file admin bs config invoke --proto-file sp-modify.txt
