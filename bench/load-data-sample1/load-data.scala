import net.koodaus.udf.ChoiceUdf
import net.koodaus.udf.DateUdf
import net.koodaus.udf.TextUdf
import net.koodaus.algo.CharClassSet
import java.time.LocalDate

val userKey = "password"

val udf_num1 = new TextUdf(userKey, 10L, CharClassSet.ONLY_NUMBERS, 10, 10)
spark.udf.register("udf_num1", (position: Long) => { udf_num1.word(position) })

val udf_num2 = new TextUdf(userKey, 11L, CharClassSet.ONLY_NUMBERS, 10, 10)
spark.udf.register("udf_num2", (position: Long) => { udf_num2.word(position) })

val udf_fname1 = new TextUdf(userKey, 20L, CharClassSet.ONLY_NUMBERS, 7, 7)
spark.udf.register("udf_fname1", (position: Long) => { udf_fname1.word(position) + ".txt" })

val udf_rus1 = new TextUdf(userKey, 30L, CharClassSet.ONLY_RUSSIAN, 15, 50)
spark.udf.register("udf_rus1", (position: Long) => { udf_rus1.phrase(position) })

val udf_rus2 = new TextUdf(userKey, 40L, CharClassSet.DEFAULT_RUSSIAN, 80, 120)
spark.udf.register("udf_rus2", (position: Long) => { udf_rus2.phrase(position) })

val udf_rus3 = new TextUdf(userKey, 50L, CharClassSet.DEFAULT_RUSSIAN, 100, 500)
spark.udf.register("udf_rus3", (position: Long) => { udf_rus3.phrase(position) })

val udf_rus4 = new TextUdf(userKey, 60L, CharClassSet.DEFAULT_RUSSIAN, 80, 120)
spark.udf.register("udf_rus4", (position: Long) => { udf_rus4.phrase(position) })

val udf_dt1 = new DateUdf(userKey, LocalDate.of(2024,1,8), LocalDate.of(2024,11,17))
spark.udf.register("udf_dt1", (position: Long) => { udf_dt1.nextString(position) + "T00:00:00.000000Z"})

val udf_edtype = new ChoiceUdf(userKey)
val edDocTypes = Array("ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101","ED101", "ED108","ED742","ED999","ED210","ED275","ED103","ED113")
spark.udf.register("udf_edtype", (position: Long) => { udf_edtype.chooseText(position, edDocTypes:_*) })


val df1 = spark.sql("""
WITH t(a) AS (VALUES
  (0),(1),(2),(3),(4),(5),(6),(7),(8),(9),
  (10),(11),(12),(13),(14),(15),(16),(17),(18),(19)),
     q(a) AS (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9)),
     qq(a) AS (SELECT q2.a*10 + q1.a FROM q q1, q q2),
     qqq(a) AS (SELECT q3.a*100 + q2.a*10 + q1.a FROM q q1, q q2, q q3),
     qqqqqq(a) AS (SELECT q2.a*1000 + q1.a FROM qqq q1, qqq q2 LIMIT 100000),
     q2k(a) AS (SELECT t.a*10000000 + q.a*1000000 + qqqqqq.a FROM t, q, qqqqqq)
SELECT
  substring(base64(unhex(replace(uuid(),'-',''))),1,22) AS id,
  substring(base64(unhex(replace(uuid(),'-',''))),1,22) AS c1,
  dt AS dt,
  dt AS creation_dt,
  dt AS value_dt,
  dt AS exec_dt,
  dt AS processing_dt,
  tv AS sys_crt_dttm,
  tv + (random() * 3600) * INTERVAL 1 SECOND AS sys_upd_dttm,
  CAST(c + 90000000 AS String) AS num,
  'GfNJaLeWRnegJ2vg4emIjA' AS acc_dt_id,
  '4nnp8bleTo-6Cm18cGTqhA' AS acc_kt_id,
  'GfNJaLeWRnegJ2vg4emIjA' AS xx_dt_acc_id,
  '30232810400000911911' AS xx_dt_acc_num,
  'ACpFLkezRaaAkpHpWYqzrA' AS xx_dt_bank_id,
  amount AS amount,
  amount AS amount_kt,
  amount AS amount_nt,
  sys_state AS sys_state,
  buh_state AS buh_state,
  'O' AS bank_direction,
  'K6VOlM_KRDGUqcDHVYf02Q' AS branch_id,
  '26z1F91RRqiYd0jYrRcgkA' AS depart_id,
  'XwlzWif4RQmUyqg1LPEgYQ' AS xxx_channel_id,
  'wpYCsiKDTuirwfrGlbJrkA' AS xxx_contract_id,
  'HgPkTE3aQUCt8s8jGywNhQ' AS kind_id,
  'RUB' AS cur,
  'RUB' AS cur_kt,
  udf_num1(a) AS src_part,
  udf_num2(a) AS dst_part,
  udf_edtype(a) AS dst_type,
  udf_fname1(c/500) AS in_file_name,
  udf_rus4(a) AS purpose,
  encode('АХТУНГ ' || udf_rus3(a), 'UTF-8') AS base_data
FROM (
  SELECT x.*,
    to_timestamp(x.dt) + (random() * 54000) * INTERVAL 1 SECOND AS tv
  FROM (SELECT
    CAST(random() * 1000000 AS Decimal(20,2)) AS amount,
    'S_14' AS sys_state,
    'PROV' AS buh_state,
    udf_dt1(DIV(a,1000000)) AS dt,
    a, div(a,1000000) AS b, mod(a,1000000) AS c
  FROM (SELECT /*+ REPARTITION(24) */ a FROM q2k) AS y) AS x
);
""")

spark.time(df1.write.mode("append")
  .option("method", "BULK_UPSERT")
  .option("write.retry.count","20")
  .option("batch.rows", "2000")
  .saveAsTable("my_ydb.bigtab1"))

spark.time(df1.write.mode("append")
  .option("method", "UPSERT")
  .option("write.retry.count","20")
  .option("batch.rows", "2000")
  .saveAsTable("my_ydb.bigtab1"))

spark.time(df1.write.mode("append")
  .option("method", "UPSERT")
  .option("write.retry.count","20")
  .option("batch.rows", "2000")
  .saveAsTable("my_ydb.bigtab2"))
