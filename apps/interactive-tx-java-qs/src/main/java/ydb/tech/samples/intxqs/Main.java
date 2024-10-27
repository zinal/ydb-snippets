package ydb.tech.samples.intxqs;

import java.util.Arrays;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.query.QueryTransaction;
import tech.ydb.query.result.QueryInfo;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.scheme.SchemeClient;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.ListType;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructType;

/**
 *
 * @author mzinal
 */
public class Main implements Runnable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(Main.class);

    private final YdbConnector connector;

    public Main(YdbConnector connector) {
        this.connector = connector;
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
        getRetryCtx().supplyResult(session
                -> session.createQuery(statement, TxMode.NONE).execute())
                .join().getStatus().expectSuccess();
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
                session.beginTransaction(TxMode.SERIALIZABLE_RW)
                    .thenApply(r -> interactiveBody(r.getValue())))
                .join().expectSuccess();
        LOG.info("Completed interactive transaction");
    }

    private Status interactiveBody(QueryTransaction tx) {
        LOG.info("Start of interactive transaction body");

        final String insertA = "UPSERT INTO `interactive-tx/table-a` "
                + "SELECT * FROM AS_TABLE($input);";
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
        
        Result<QueryInfo> result = tx.createQuery(insertA, paramsA).execute().join();
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        LOG.info("Statement 1 successful, transaction id {}", tx.getId());

        final String insertB = "UPSERT INTO `interactive-tx/table-b` "
                + "SELECT * FROM AS_TABLE($input);";
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
        result = tx.createQuery(insertB, paramsB).execute().join();
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        LOG.info("Statement 2 successful, transaction continues");

        final String insertC = "UPSERT INTO `interactive-tx/table-c` "
                + "SELECT * FROM AS_TABLE($input);";
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
        result = tx.createQuery(insertC, paramsC).execute().join();
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        LOG.info("Statement 3 successful, transaction committed");
        return Status.SUCCESS;
    }

    public static void main(String[] args) {
        LOG.info("YDB Interactive Transaction Example");
        String configFile = "example1.xml";
        if (args.length > 0) {
            configFile = args[0];
        }
        try {
            YdbConnector.Config ycc = YdbConnector.Config.fromFile(configFile);
            try (YdbConnector yc = new YdbConnector(ycc)) {
                new Main(yc).run();
            }
        } catch (Exception ex) {
            LOG.error("FAILURE", ex);
            System.exit(1);
        }
    }

}
