# Spark job to read data from topic and write it to the table

## Topic creation

```bash
ydb topic create mytopic1
ydb topic consumer add --consumer c1 mytopic1
```

## Writing data to the topic

```bash
for i in `seq 1 100000`; do echo "message-$i"; done | ydb topic write --format newline-delimited mytopic1
```

Sample code to validate data can be read from the topic:

```bash
ydb topic read --consumer c1 --limit 1 mytopic1
```

## Table creation

```sql
CREATE TABLE mycoltab1 (
  ts Timestamp not null,
  pos Int32 not null,
  id Text not null,
  batch_id Int64,
  msg Text,
  PRIMARY KEY(ts, pos, id)
) WITH(STORE=COLUMN)'
```

## Spark Shell submission

```bash
# Ensure the checkpoint directory exists
mkdir -pv /tmp/ydb-mytopic-cp1
# Dependency version depends on Spark version
./bin/spark-shell --packages "org.apache.spark:spark-streaming-kafka-0-10_2.12:3.5.5,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5"
```

## Spark properties for YDB connection

```
spark.sql.catalog.ydb1                tech.ydb.spark.connector.YdbCatalog
spark.sql.catalog.ydb1.url            grpcs://ydb-1.front.private:2135/cluster1/testdb
spark.sql.catalog.ydb1.auth.mode      STATIC
spark.sql.catalog.ydb1.auth.login     root
spark.sql.catalog.ydb1.auth.password  ***
spark.sql.catalog.ydb1.ca.file        /home/demo/ydb-cluster1-ca.crt
```

## Spark Scala code for stream processing

```scala
import org.apache.spark.sql.streaming.Trigger
import org.apache.spark.sql.functions.current_timestamp
import org.apache.spark.sql.functions.expr
import org.apache.spark.sql.functions.lit
import org.apache.spark.sql.functions.row_number
import org.apache.spark.sql.Dataset
import org.apache.spark.sql.Row
import org.apache.spark.sql.expressions.Window

// function to save portion of data to ydb table
def saveToYdb = (df: Dataset[Row], batchId: Long) => {
  (df
    .withColumn("ts", current_timestamp())
    .withColumn("pos", row_number().over(Window.orderBy(lit('A'))))
    .withColumn("id", expr("substring(base64(unhex(replace(uuid(),'-',''))),1,22)"))
    .withColumn("batch_id", lit(batchId))
  ).write.option("method", "bulk").mode("append").saveAsTable("ydb1.mycoltab1")
}

// read the certificate from file to string
val ydbCert = scala.io.Source.fromFile("/home/demo/ydb-cluster1-ca.crt").mkString

// connect to ydb topic
val df = (spark.readStream.format("kafka")
  .option("kafka.bootstrap.servers", "ydb-1.front.private:9093,ydb-2.front.private:9093,ydb-3.front.private:9093")
  .option("subscribe", "mytopic1")
  .option("kafka.group.id", "c1")
  .option("kafka.check.crcs", "false")
  .option("kafka.partition.assignment.strategy", "org.apache.kafka.clients.consumer.RoundRobinAssignor")
  .option("kafka.security.protocol", "SASL_SSL")
  .option("kafka.sasl.mechanism", "PLAIN")
  .option("kafka.ssl.truststore.type", "PEM")
  .option("kafka.ssl.truststore.certificates", ydbCert)
  .option("kafka.sasl.jaas.config", "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"root@/cluster1/testdb\" password=\"P@$$w0rd+\";")
  .load()
  .selectExpr("CAST(value AS STRING) AS msg"))

// process and write data to ydb table in batches
(df.writeStream
  .outputMode("append")
  .trigger(Trigger.ProcessingTime("10 seconds"))
  .foreachBatch(saveToYdb)
  .start()
  .awaitTermination())

```

## Spark Scala code for batch topic data processing

```scala
val ydbCert = scala.io.Source.fromFile("/home/demo/ydb-cluster1-ca.crt").mkString

val df = (spark.read.format("kafka")
  .option("kafka.bootstrap.servers", "ydb-1.front.private:9093,ydb-2.front.private:9093,ydb-3.front.private:9093")
  .option("subscribe", "mytopic1")
  .option("kafka.group.id", "c1")
  .option("kafka.check.crcs", "false")
  .option("kafka.partition.assignment.strategy", "org.apache.kafka.clients.consumer.RoundRobinAssignor")
  .option("kafka.security.protocol", "SASL_SSL")
  .option("kafka.sasl.mechanism", "PLAIN")
  .option("kafka.ssl.truststore.type", "PEM")
  .option("kafka.ssl.truststore.certificates", ydbCert)
  .option("kafka.sasl.jaas.config", "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"root@/cluster1/testdb\" password=\"P@$$w0rd+\";")
  .load())

(df.selectExpr("CAST(key AS STRING)", "CAST(value AS STRING)")
  .as[(String, String)]).show(10, false)

```
