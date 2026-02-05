
CREATE TABLE dict_doctype (
    id Text NOT NULL,
    code Text NOT NULL,
    name Text NOT NULL,
    PRIMARY KEY(id),
    INDEX ix_code GLOBAL SYNC ON (code) COVER (name)
);

CREATE TABLE mv1 (
	id	Utf8 NOT NULL,
	c1	Utf8,
	dt	Utf8,
    PRIMARY KEY(id),
    INDEX ix_c1 GLOBAL SYNC ON (c1) COVER (dt),
    INDEX ix_dt GLOBAL SYNC ON (dt) COVER (c1)
) WITH (
    AUTO_PARTITIONING_BY_LOAD = ENABLED,
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 100,
    AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 200,
    PARTITION_AT_KEYS = (
      '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
      'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
      'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
      'U', 'V', 'W', 'X', 'Y', 'Z',
      'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
      'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
      'u', 'v', 'w', 'x', 'y', 'z')
);

CREATE TABLE mv2 (
	id	Utf8 NOT NULL,
	value_dt	Timestamp64,
	sys_crt_dttm	Timestamp64,
	sys_upd_dttm	Timestamp64,
	src_part	Utf8,
	dst_part	Utf8,
    dst_type Utf8,
    dst_name Utf8,
    PRIMARY KEY(id)
) WITH (
    AUTO_PARTITIONING_BY_LOAD = ENABLED,
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_PARTITION_SIZE_MB = 2048,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 100,
    AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 200,
    PARTITION_AT_KEYS = (
      '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
      'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
      'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
      'U', 'V', 'W', 'X', 'Y', 'Z',
      'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
      'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
      'u', 'v', 'w', 'x', 'y', 'z')
);
