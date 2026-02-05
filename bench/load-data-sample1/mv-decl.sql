CREATE ASYNC MATERIALIZED VIEW mv1 AS
  SELECT
      main.id AS id,
      main.c1 AS c1,
      main.dt AS dt
  FROM `bigtab1` AS main
  WHERE COMPUTE ON main.id #[ 3 = (Digest::CityHash(main.id) % 10) ]#;

CREATE ASYNC MATERIALIZED VIEW mv2 AS
  SELECT
      main.id AS id,
      main.value_dt AS value_dt,
      main.sys_crt_dttm AS sys_crt_dttm,
      main.sys_upd_dttm AS sys_upd_dttm,
      main.src_part AS src_part,
      main.dst_part AS dst_part,
      main.dst_type AS dst_type,
      dict.name AS dst_name
  FROM `bigtab1` AS main
  INNER JOIN `dict_doctype` AS dict
    ON main.dst_type = dict.code;
  WHERE COMPUTE ON main.id #[ 0 = (Digest::CityHash(main.id) % 2) ]#;

CREATE ASYNC MATERIALIZED VIEW mv3 AS
  SELECT
      main.id AS id,
      main.value_dt AS value_dt,
      main.sys_crt_dttm AS sys_crt_dttm,
      main.sys_upd_dttm AS sys_upd_dttm,
      main.src_part AS src_part,
      main.dst_part AS dst_part,
      main.dst_type AS dst_type,
      dict.name AS dst_name
  FROM `bigtab1` AS main
  INNER JOIN `dict_doctype` AS dict
    ON main.dst_type = dict.code;
  WHERE COMPUTE ON main.id #[ 1 = (Digest::CityHash(main.id) % 2) ]#;

CREATE ASYNC HANDLER h1 CONSUMER h1_consumer
  PROCESS mv1,
  PROCESS mv2,
  INPUT bigtab1 CHANGEFEED mv AS STREAM,
  INPUT dict_doctype CHANGEFEED mv AS BATCH;

CREATE ASYNC HANDLER h2 CONSUMER h2_consumer
  PROCESS mv3
  INPUT bigtab1 CHANGEFEED mv AS STREAM,
  INPUT dict_doctype CHANGEFEED mv AS BATCH;
