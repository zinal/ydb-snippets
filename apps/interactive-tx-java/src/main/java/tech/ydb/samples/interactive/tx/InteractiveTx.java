package tech.ydb.samples.interactive.tx;

import java.util.Arrays;
import java.util.concurrent.CompletableFuture;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.scheme.SchemeClient;
import tech.ydb.table.SessionRetryContext;
import tech.ydb.table.query.DataQueryResult;
import tech.ydb.table.query.Params;
import tech.ydb.table.result.ResultSetReader;
import tech.ydb.table.settings.ExecuteDataQuerySettings;
import tech.ydb.table.transaction.TableTransaction;
import tech.ydb.table.values.ListType;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructType;

/**
 * YDB native SDK samples - interactive read/write transaction example.
 *
 * @author mzinal
 */
public class InteractiveTx implements Runnable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(InteractiveTx.class);

    private final YdbConnector connector;

    public InteractiveTx(YdbConnector yc) {
        this.connector = yc;
    }

    private SessionRetryContext getRetryCtx() {
        return connector.getRetryCtx();
    }

    private SchemeClient getSchemeClient() {
        return connector.getSchemeClient();
    }

    @Override
    public void run() {
        createTables();
        interactiveTransaction();
        dropTables();
    }

    private void runDdl(String statement) {
        getRetryCtx().supplyStatus(session -> session.executeSchemeQuery(statement))
                .join().expectSuccess();
    }

    private void createTables() {
        runDdl("CREATE TABLE `interactive-tx/table-a`(a Int32 NOT NULL, "
                + "  b Int32, c Utf8, PRIMARY KEY(a), "
                + "  INDEX ix_b GLOBAL ON (b))");
        runDdl("CREATE TABLE `interactive-tx/table-b`(b Int32 NOT NULL, "
                + "  c Text, PRIMARY KEY(b))");
        runDdl("CREATE TABLE `interactive-tx/table-c`(a Int32 NOT NULL, "
                + "  b Int32, PRIMARY KEY(b), "
                + "  INDEX ix_a GLOBAL ON (a))");
        LOG.info("Tables created.");
    }

    private void dropTables() {
        runDdl("DROP TABLE `interactive-tx/table-a`");
        runDdl("DROP TABLE `interactive-tx/table-b`");
        runDdl("DROP TABLE `interactive-tx/table-c`");
        LOG.info("Tables dropped.");
        getSchemeClient().removeDirectory("interactive-tx");
        LOG.info("Directory removed.");
    }

    private void interactiveTransaction() {
        LOG.info("Start of interactive transaction");
        getRetryCtx().supplyStatus(session ->
                asyncBody(session.createNewTransaction(TxMode.SERIALIZABLE_RW)))
                .join().expectSuccess();
        LOG.info("Completed interactive transaction");
    }

    private CompletableFuture<Status> asyncBody(TableTransaction tx) {
        return CompletableFuture.completedFuture(interactiveBody(tx));
    }

    private Status interactiveBody(TableTransaction tx) {
        LOG.info("Start of interactive transaction body");

        final String insertA = "DECLARE $input AS List<Struct<a:Int32,b:Int32,c:Utf8>>;"
                + "UPSERT INTO `interactive-tx/table-a` SELECT * FROM AS_TABLE($input);";
        final StructType structA = StructType.of(
                "a", PrimitiveType.Int32,
                "b", PrimitiveType.Int32,
                "c", PrimitiveType.Text);
        final Params paramsA = Params.of("$input", ListType.of(structA)
                .newValue(Arrays.asList(
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(1),
                                "b", PrimitiveValue.newInt32(10),
                                "c", PrimitiveValue.newText("value 100")),
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(2),
                                "b", PrimitiveValue.newInt32(20),
                                "c", PrimitiveValue.newText("value 200")),
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(3),
                                "b", PrimitiveValue.newInt32(30),
                                "c", PrimitiveValue.newText("value 300"))
                )));
        Result<DataQueryResult> dqr = tx.executeDataQuery(insertA, paramsA).join();
        if (! dqr.isSuccess()) {
            return dqr.getStatus();
        }

        LOG.info("Statement 1 successful, transaction id {}", tx.getId());

        final String insertB = "DECLARE $input AS List<Struct<b:Int32,c:Utf8>>;"
                + "UPSERT INTO `interactive-tx/table-b` SELECT * FROM AS_TABLE($input);";
        final StructType structB = StructType.of(
                "b", PrimitiveType.Int32,
                "c", PrimitiveType.Text);
        final Params paramsB = Params.of("$input", ListType.of(structB)
                .newValue(Arrays.asList(
                        structB.newValue(
                                "b", PrimitiveValue.newInt32(10),
                                "c", PrimitiveValue.newText("value 100")),
                        structB.newValue(
                                "b", PrimitiveValue.newInt32(20),
                                "c", PrimitiveValue.newText("value 200")),
                        structB.newValue(
                                "b", PrimitiveValue.newInt32(30),
                                "c", PrimitiveValue.newText("value 300"))
                )));
        dqr = tx.executeDataQuery(insertB, paramsB).join();
        if (! dqr.isSuccess()) {
            return dqr.getStatus();
        }

        LOG.info("Statement 2 successful, transaction continues");

        final String insertC = "DECLARE $input AS List<Struct<a:Int32, b:Int32>>;"
                + "UPSERT INTO `interactive-tx/table-c` SELECT * FROM AS_TABLE($input);";
        final StructType structC = StructType.of(
                "a", PrimitiveType.Int32,
                "b", PrimitiveType.Int32);
        final Params paramsC = Params.of("$input", ListType.of(structC)
                .newValue(Arrays.asList(
                        structC.newValue(
                                "a", PrimitiveValue.newInt32(1),
                                "b", PrimitiveValue.newInt32(10)),
                        structC.newValue(
                                "a", PrimitiveValue.newInt32(2),
                                "b", PrimitiveValue.newInt32(20)),
                        structC.newValue(
                                "a", PrimitiveValue.newInt32(3),
                                "b", PrimitiveValue.newInt32(30))
                )));
        dqr = tx.executeDataQuery(insertC, paramsC).join();
        if (! dqr.isSuccess()) {
            return dqr.getStatus();
        }
        LOG.info("Statement 3 successful, transaction continues");

        final String select1 = "DECLARE $a AS Int32; DECLARE $b AS Int32; "
                + "SELECT COUNT(1) AS cnt "
                + "FROM `interactive-tx/table-a` AS a "
                + "INNER JOIN `interactive-tx/table-b` AS b "
                + "  ON a.b=b.b "
                + "INNER JOIN `interactive-tx/table-c` AS c "
                + "  ON a.b=c.b "
                + "WHERE a.a=$a AND a.b=$b";
        final Params paramsS = Params.of(
                "$a", PrimitiveValue.newInt32(1),
                "$b", PrimitiveValue.newInt32(10));

        dqr = tx.executeDataQuery(select1, true, paramsS, new ExecuteDataQuerySettings()).join();
        if (! dqr.isSuccess()) {
            return dqr.getStatus();
        }

        LOG.info("Statement 4 successful, transaction committed");

        ResultSetReader rs = dqr.getValue().getResultSet(0);
        rs.next();
        long nrows = rs.getColumn(0).getUint64();

        LOG.info("Output rows count: {}", nrows);

        return Status.SUCCESS;
    }

    public static void main(String[] args) {
        LOG.info("YDB Interactive Transaction Example");
        String configFile = "interactive-tx-config.xml";
        if (args.length > 0) {
            configFile = args[0];
        }
        try {
            YdbConnector.Config ycc = YdbConnector.Config.fromFile(configFile);
            try (YdbConnector yc = new YdbConnector(ycc)) {
                new InteractiveTx(yc).run();
            }
        } catch(Exception ex) {
            LOG.error("FAILURE", ex);
            System.exit(1);
        }
    }

}
