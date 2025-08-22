package tech.ydb.samples.ixconc;

import tech.ydb.common.transaction.TxMode;
import tech.ydb.query.QuerySession;
import tech.ydb.query.QueryTransaction;
import tech.ydb.query.tools.QueryReader;
import tech.ydb.table.query.Params;
import tech.ydb.table.result.ResultSetReader;
import tech.ydb.table.values.PrimitiveValue;

/**
 * YDB index concurrency demo.
 *
 * CREATE TABLE demo_settings(id Text NOT NULL, code Text, val Text, PRIMARY KEY(id), INDEX ix_code GLOBAL ON(code));
 * UPSERT INTO demo_settings(id, code, val) VALUES ("id1"u, "code1"u, "value1"u), ("id2"u, "code2"u, "value2"u);
 *
 * CREATE TABLE demo_other(id Text NOT NULL, val Text, PRIMARY KEY(id));
 *
 * @author zinal
 */
public class App {
    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(App.class);

    public static void main(String[] args) {
        if (args.length != 1) {
            System.out.println("USAGE: tech.ydb.samples.ixconc.App connect.xml");
            System.exit(1);
        }
        try {
            PrimitiveValue code1 = PrimitiveValue.newText("code1");
            PrimitiveValue code2 = PrimitiveValue.newText("code2");

            YdbConnector.Config ycc = YdbConnector.Config.fromFile(args[0]);
            try (YdbConnector conn = new YdbConnector(ycc)) {
                QuerySession qs1 = conn.createQuerySession();
                QueryTransaction trans1 = qs1.beginTransaction(TxMode.SERIALIZABLE_RW).join().getValue();

                String sql = "UPSERT INTO demo_other(id, val) VALUES('aaa'u, cast(RandomUuid(1) as Text));";
                trans1.createQuery(sql).execute().join().getStatus().expectSuccess();
                System.out.println("Transaction 1 UPSERT completed.");

                QuerySession qs2 = conn.createQuerySession();
                QueryTransaction trans2 = qs1.beginTransaction(TxMode.SERIALIZABLE_RW).join().getValue();
                sql = "UPSERT INTO demo_other(id, val) VALUES('bbb'u, cast(RandomUuid(1) as Text));";
                trans2.createQuery(sql).execute().join().getStatus().expectSuccess();
                System.out.println("Transaction 2 UPSERT 1 completed.");

                sql = "DECLARE $id AS Text; DECLARE $code AS Text; DECLARE $val AS Text; "
                        + "UPSERT INTO demo_settings(id, code, val) VALUES($id, $code, $val);";
                trans2.createQuery(sql, Params.of(
                        "$id", PrimitiveValue.newText("id2"),
                        "$code", code2,
                        "$val", PrimitiveValue.newText("somevalue2")
                )).execute().join().getStatus().expectSuccess();
                System.out.println("Transaction 2 UPSERT 2 completed.");

                trans2.commit().join().getStatus().expectSuccess();
                System.out.println("Transaction 2 COMMIT completed.");

                sql = "DECLARE $code AS Text; SELECT * FROM demo_settings WHERE code=$code;";
                ResultSetReader rs1 = QueryReader.readFrom(trans1.createQuery(sql, Params.of("$code", code1)))
                        .join().getValue().getResultSet(0);
                System.out.println("Transaction 1 SELECT completed.");
                while (rs1.next()) {
                    System.out.println("Transaction 1 SELECT output: " + rs1.getColumn("id").getText());
                }

                trans1.commit().join().getStatus().expectSuccess();
                System.out.println("Transaction 1 COMMIT completed.");

                qs1.close();
                qs2.close();
            }
        } catch(Exception ex) {
            LOG.error("Execution failed", ex);
        }
    }

}
