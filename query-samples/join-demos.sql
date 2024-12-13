-- Вариант 1

CREATE TABLE `KIKIMR-22355/tab1` (
    id Text NOT NULL,
    dst_ident Text,
    exec_dt Timestamp,
    PRIMARY KEY(id),
    INDEX ix_exec_dt GLOBAL ON (exec_dt)
);

CREATE TABLE `KIKIMR-22355/tab2` (
    id Text NOT NULL,
    int_ref Text,
    ext_ref Text,
    send_dttm Timestamp,
    PRIMARY KEY(id),
    INDEX ix_int_ref GLOBAL ON (int_ref),
    INDEX ix_ext_ref GLOBAL ON (ext_ref),
    INDEX ix_send_dttm GLOBAL ON (send_dttm)
);

UPSERT INTO `KIKIMR-22355/tab1` (id, dst_ident, exec_dt) VALUES
  ('t1-0'u, 'id-1'u, Timestamp('2024-12-03T01:00:00.000000Z')),
  ('t1-1'u, 'id-2'u, Timestamp('2024-12-03T02:00:00.000000Z')),
  ('t1-2'u, 'id-3'u, Timestamp('2024-12-03T03:00:00.000000Z'));

UPSERT INTO `KIKIMR-22355/tab2` (id, int_ref, ext_ref, send_dttm) VALUES
  ('t2-0'u, 't1-0'u, 'id-1'u, Timestamp('2024-12-03T01:01:00.000000Z')),
  ('t2-1'u, 't1-0'u, null, Timestamp('2024-12-03T02:01:00.000000Z')),
  ('t2-2'u, 't1-0'u, null, Timestamp('2024-12-03T02:01:00.000000Z')),
  ('t2-3'u, 't1-1'u, 'id-2'u, Timestamp('2024-12-03T03:01:00.000000Z')),
  ('t2-4'u, 't1-1'u, null, Timestamp('2024-12-03T04:01:00.000000Z')),
  ('t2-5'u, 't1-1'u, null, Timestamp('2024-12-03T05:01:00.000000Z')),
  ('t2-6'u, 't1-2'u, 'id-3'u, Timestamp('2024-12-03T06:01:00.000000Z')),
  ('t2-7'u, 't1-2'u, null, Timestamp('2024-12-03T07:01:00.000000Z')),
  ('t2-8'u, 't1-2'u, null, Timestamp('2024-12-03T08:01:00.000000Z')),
  ('t2-9'u, 't1-2'u, null, Timestamp('2024-12-03T09:01:00.000000Z'));

$sys_date = DateTime("2024-12-03T00:00:00Z");
$ival = DateTime::IntervalFromDays(1);
SELECT doc.id, req.id, doc.dst_ident, req.ext_ref
FROM `KIKIMR-22355/tab1` VIEW ix_exec_dt AS doc
LEFT JOIN `KIKIMR-22355/tab2` VIEW ix_int_ref req
ON doc.id = req.int_ref AND doc.dst_ident = req.ext_ref
WHERE doc.exec_dt >= $sys_date and doc.exec_dt <$sys_date + $ival
  AND doc.id='t1-1'u;

-- Вариант 2

CREATE TABLE `KIKIMR-22355/tab3` (
    id Text NOT NULL,
    dst_ident Text,
    exec_dt Timestamp,
    PRIMARY KEY(id),
    INDEX ix_exec_dt GLOBAL ON (exec_dt)
);

CREATE TABLE `KIKIMR-22355/tab4` (
    id Text NOT NULL,
    int_ref Text,
    ext_ref Text,
    good_sign Text,
    send_dttm Timestamp,
    PRIMARY KEY(id),
    INDEX ix_int_ref GLOBAL ON (int_ref),
    INDEX ix_ext_ref GLOBAL ON (ext_ref),
    INDEX ix_send_dttm GLOBAL ON (send_dttm)
);

UPSERT INTO `KIKIMR-22355/tab3` (id, dst_ident, exec_dt) VALUES
  ('t1-0'u, 'id-1'u, Timestamp('2024-12-03T01:00:00.000000Z')),
  ('t1-1'u, 'id-2'u, Timestamp('2024-12-03T02:00:00.000000Z')),
  ('t1-2'u, 'id-3'u, Timestamp('2024-12-03T03:00:00.000000Z'));

UPSERT INTO `KIKIMR-22355/tab4` (id, int_ref, ext_ref, good_sign, send_dttm) VALUES
  ('t2-0'u, 't1-0'u, 'id-1'u, 'GOOD'u, Timestamp('2024-12-03T01:01:00.000000Z')),
  ('t2-1'u, 't1-0'u, null, 'BAD'u, Timestamp('2024-12-03T02:01:00.000000Z')),
  ('t2-2'u, 't1-0'u, null, 'BAD'u, Timestamp('2024-12-03T02:01:00.000000Z')),
  ('t2-3'u, 't1-1'u, 'id-2'u, 'GOOD'u, Timestamp('2024-12-03T03:01:00.000000Z')),
  ('t2-4'u, 't1-1'u, null, 'BAD'u, Timestamp('2024-12-03T04:01:00.000000Z')),
  ('t2-5'u, 't1-1'u, null, 'BAD'u, Timestamp('2024-12-03T05:01:00.000000Z')),
  ('t2-6'u, 't1-2'u, 'id-3'u, 'GOOD'u, Timestamp('2024-12-03T06:01:00.000000Z')),
  ('t2-7'u, 't1-2'u, null, 'BAD'u, Timestamp('2024-12-03T07:01:00.000000Z')),
  ('t2-8'u, 't1-2'u, null, 'BAD'u, Timestamp('2024-12-03T08:01:00.000000Z')),
  ('t2-9'u, 't1-2'u, null, 'BAD'u, Timestamp('2024-12-03T09:01:00.000000Z'));

$sys_date = DateTime("2024-12-03T00:00:00Z");
$ival = DateTime::IntervalFromDays(1);
SELECT doc.id, req.id, doc.dst_ident, req.ext_ref, req.good_sign
FROM `KIKIMR-22355/tab3` VIEW ix_exec_dt AS doc
LEFT JOIN (
    SELECT id, int_ref, ext_ref, good_sign
    FROM `KIKIMR-22355/tab4` VIEW ix_int_ref
    WHERE good_sign='GOOD'u
) AS req
  ON doc.id = req.int_ref AND doc.dst_ident = req.ext_ref
WHERE doc.exec_dt >= $sys_date and doc.exec_dt <$sys_date + $ival
  AND doc.id='t1-1'u;

-- Вариант 3

CREATE TABLE `KIKIMR-22355/tab5` (
    id Text NOT NULL,
    ref_coll Text,
    exec_dt Timestamp,
    PRIMARY KEY(id),
    INDEX ix_exec_dt GLOBAL ON (exec_dt),
    INDEX ix_ref_coll GLOBAL ON (ref_coll)
);

CREATE TABLE `KIKIMR-22355/tab6` (
    main_id Text NOT NULL,
    collection_id Text,
    link_type_id Text,
    PRIMARY KEY(main_id, collection_id)
);

UPSERT INTO `KIKIMR-22355/tab5` (id, ref_coll, exec_dt) VALUES
  ('k00'u, null,   Timestamp('2024-12-03T01:00:00.000000Z')),
  ('k01'u, null,   Timestamp('2024-12-03T01:00:00.000000Z')),
  ('k02'u, null,   Timestamp('2024-12-03T01:00:00.000000Z')),
  ('k03'u, null,   Timestamp('2024-12-03T01:00:00.000000Z')),
  ('k04'u, null,   Timestamp('2024-12-03T01:00:00.000000Z')),
  ('k10'u, 'c00'u, Timestamp('2024-12-03T01:00:00.000000Z'));

UPSERT INTO `KIKIMR-22355/tab6` (main_id, collection_id, link_type_id) VALUES
  ('k00'u, 'c00'u, 'l00'u),
  ('k01'u, 'c00'u, 'l00'u),
  ('k02'u, 'c00'u, 'l00'u),
  ('k03'u, 'c00'u, 'l00'u),
  ('k04'u, 'c00'u, 'l00'u);

SELECT COUNT(*) FROM (
    SELECT t5.*, t6.*
    FROM `KIKIMR-22355/tab5` AS t5
    LEFT JOIN (
        SELECT * FROM `KIKIMR-22355/tab6` WHERE link_type_id='l00'u
    ) AS t6 ON t5.id=t6.main_id
    LEFT JOIN `KIKIMR-22355/tab5` VIEW ix_ref_coll AS t5owner
    ON t6.collection_id=t5owner.ref_coll
) WHERE exec_dt BETWEEN DateTime("2024-12-03T00:00:00Z") AND DateTime("2024-12-05T00:00:00Z");
