ydb yql -s 'DROP TABLE `stroppy/transfer`'

ydb yql -s 'CREATE TABLE `stroppy/transfer` (
transfer_id	String,
src_bic	String,
src_ban	String,
dst_bic	String,
dst_ban	String,
amount	Int64,
state	String,
client_id	String,
client_timestamp	Timestamp,
PRIMARY KEY(transfer_id)
) WITH(
  AUTO_PARTITIONING_BY_LOAD = ENABLED,
  AUTO_PARTITIONING_BY_SIZE = ENABLED,
  AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 300,
  AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 350,
  PARTITION_AT_KEYS = ("1","2","3","4","5","6","7","8","9","a","b","c","d","e","f")
);'

