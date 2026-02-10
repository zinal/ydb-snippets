CREATE ASYNC MATERIALIZED VIEW mv1 AS
  SELECT
      main0.id AS id,
      main0.c1 AS c1,
      main0.dt AS dt,
      main1.in_file_name AS in_file_name_2,
      main1.purpose AS purpose_2
  FROM `bigtab1` AS main0
  INNER JOIN `bigtab2` AS main1
    ON main0.c1 = main1.c1
  WHERE COMPUTE ON main0.id #[ 3 = (Digest::CityHash(main0.id) % 10) ]#;

CREATE ASYNC MATERIALIZED VIEW mv2
  DESTINATION `destination1` AS
  SELECT
      main1.id AS id,
      main1.value_dt AS value_dt,
      main1.sys_crt_dttm AS sys_crt_dttm,
      main1.sys_upd_dttm AS sys_upd_dttm,
      main1.src_part AS src_part,
      main1.dst_part AS dst_part,
      main1.dst_type AS dst_type,
      dict1.name AS dst_name
  FROM `bigtab1` AS main1
  INNER JOIN `dict_doctype` AS dict1
    ON main1.dst_type = dict1.code
  WHERE COMPUTE ON main1.id #[ 0 = (Digest::CityHash(main1.id) % 2) ]#;

CREATE ASYNC MATERIALIZED VIEW mv3
  DESTINATION `destination1` AS
  SELECT
      main2.id AS id,
      main2.value_dt AS value_dt,
      main2.sys_crt_dttm AS sys_crt_dttm,
      main2.sys_upd_dttm AS sys_upd_dttm,
      main2.src_part AS src_part,
      main2.dst_part AS dst_part,
      main2.dst_type AS dst_type,
      dict2.name AS dst_name,
      main1.in_file_name AS in_file_name_2,
      main1.purpose AS purpose_2
  FROM `bigtab1` AS main2
  INNER JOIN `bigtab2` AS main1
    ON main2.c1 = main1.c1
  INNER JOIN `dict_doctype` AS dict2
    ON main2.dst_type = dict2.code
  WHERE COMPUTE ON main2.id #[ 1 = (Digest::CityHash(main2.id) % 2) ]#;

CREATE ASYNC HANDLER h1 CONSUMER h1_consumer
  PROCESS mv1,
  PROCESS mv2,
  INPUT bigtab1 CHANGEFEED mv AS STREAM,
  INPUT bigtab2 CHANGEFEED mv AS STREAM,
  INPUT dict_doctype CHANGEFEED mv AS BATCH;

CREATE ASYNC HANDLER h2 CONSUMER h2_consumer
  PROCESS mv3,
  INPUT bigtab1 CHANGEFEED mv AS STREAM,
  INPUT bigtab2 CHANGEFEED mv AS STREAM,
  INPUT dict_doctype CHANGEFEED mv AS BATCH;
