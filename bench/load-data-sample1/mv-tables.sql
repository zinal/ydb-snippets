
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
    in_file_name_2 Utf8,
    purpose_2 Utf8,
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

CREATE TABLE mv3 (
	id	Utf8 NOT NULL,
	value_dt	Timestamp64,
	sys_crt_dttm	Timestamp64,
	sys_upd_dttm	Timestamp64,
	src_part	Utf8,
	dst_part	Utf8,
    dst_type Utf8,
    dst_name Utf8,
    in_file_name_2 Utf8,
    purpose_2 Utf8,
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

-- *** work tables for job controller and runners ***

-- MV definitions
CREATE TABLE `mv/statements` (
   statement_no Int32 NOT NULL,
   statement_text Text NOT NULL,
   PRIMARY KEY(statement_no)
);

-- Externally controlled job definitions
CREATE TABLE `mv/jobs` (
    job_name Text NOT NULL,
    job_settings JsonDocument,
    should_run Bool,
    PRIMARY KEY(job_name)
);

-- Externally controlled scan requests
CREATE TABLE `mv/job_scans` (
    job_name Text NOT NULL,
    target_name Text NOT NULL,
    scan_settings JsonDocument,
    requested_at Timestamp,
    accepted_at Timestamp,
    runner_id Text,
    command_no Uint64,
    PRIMARY KEY(job_name, target_name)
);

-- *** Working tables ***

-- Dictionary changelog table
CREATE TABLE `mv/dict_hist` (
   src Text NOT NULL,
   tv Timestamp NOT NULL,
   seqno Uint64 NOT NULL,
   key_text Text NOT NULL,
   key_val JsonDocument,
   diff_val JsonDocument,
   PRIMARY KEY(src, tv, seqno, key_text)
);

-- Scans state table
CREATE TABLE `mv/scans_state` (
   job_name Text NOT NULL,
   table_name Text NOT NULL,
   updated_at Timestamp,
   key_position JsonDocument,
   PRIMARY KEY(job_name, table_name)
);

-- Runner instances status
CREATE TABLE `mv/runners` (
    runner_id Text NOT NULL,
    runner_identity Text,
    updated_at Timestamp,
    PRIMARY KEY(runner_id)
);

-- Jobs, per runner instance
CREATE TABLE `mv/runner_jobs` (
    runner_id Text NOT NULL,
    job_name Text NOT NULL,
    job_settings JsonDocument,
    started_at Timestamp,
    INDEX ix_job_name GLOBAL SYNC ON (job_name),
    PRIMARY KEY(runner_id, job_name)
);

-- Command control table via controller and runners
CREATE TABLE `mv/commands` (
    runner_id Text NOT NULL,
    command_no Uint64 NOT NULL,
    created_at Timestamp,
    command_type Text, -- START / STOP / SCAN / NOSCAN
    job_name Text,
    target_name Text,
    job_settings JsonDocument,
    command_status Text, -- CREATED / TAKEN / SUCCESS / ERROR
    command_diag Text,
    INDEX ix_command_no GLOBAL SYNC ON (command_no),
    INDEX ix_command_status GLOBAL SYNC ON (command_status, runner_id),
    PRIMARY KEY(runner_id, command_no)
);

UPSERT INTO `mv/jobs`(job_name, should_run) VALUES ('h1', true), ('h2', true);
UPSERT INTO `mv/jobs`(job_name, should_run) VALUES ('ydbmv$dictionary', true);
