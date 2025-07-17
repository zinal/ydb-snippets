package ydb.tech.samples.ts64;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.query.QueryTransaction;
import tech.ydb.query.result.QueryInfo;
import tech.ydb.query.tools.QueryReader;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.scheme.SchemeClient;
import tech.ydb.table.query.Params;
import tech.ydb.table.result.ResultSetReader;
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
        runDdl("CREATE TABLE `ts64-test/table-a`(a Int32 NOT NULL, "
                + "  b Timestamp64, c Date32, PRIMARY KEY(a), "
                + "  INDEX ix_b GLOBAL ON (b), INDEX ix_c GLOBAL ON (c))");
        LOG.info("Table created.");
    }

    private void dropTables() {
        runDdl("DROP TABLE `ts64-test/table-a`");
        LOG.info("Table dropped.");
        getSchemeClient().removeDirectory("ts64-test");
        LOG.info("Directory removed.");
    }

    private void interactiveTransaction() {
        LOG.info("Start of transaction");
        getRetryCtx().supplyStatus(session ->
                session.beginTransaction(TxMode.SERIALIZABLE_RW)
                    .thenApply(r -> interactiveBody(r.getValue())))
                .join().expectSuccess();
        LOG.info("Completed transaction");
    }

    private Status interactiveBody(QueryTransaction tx) {
        LOG.info("Start of transaction body");

        final String insertA = "DECLARE $input AS List<Struct<"
                + "a:Int32,b:Timestamp64,c:Date32>>; "
                + "UPSERT INTO `ts64-test/table-a` SELECT * FROM AS_TABLE($input);";
        final StructType structA = StructType.of(
                "a", PrimitiveType.Int32,
                "b", PrimitiveType.Timestamp64,
                "c", PrimitiveType.Date32);
        Instant now = Instant.now();
        final Params paramsA = Params.of("$input", ListType.of(structA)
                .newValue(Arrays.asList(
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(1),
                                "b", PrimitiveValue.newTimestamp64(now.minus(1L, ChronoUnit.HOURS)),
                                "c", PrimitiveValue.newDate32(now.minus(1L, ChronoUnit.DAYS).atZone(ZoneId.systemDefault()).toLocalDate())),
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(2),
                                "b", PrimitiveValue.newTimestamp64(now.minus(2L, ChronoUnit.HOURS)),
                                "c", PrimitiveValue.newDate32(now.minus(2L, ChronoUnit.DAYS).atZone(ZoneId.systemDefault()).toLocalDate())),
                        structA.newValue(
                                "a", PrimitiveValue.newInt32(3),
                                "b", PrimitiveValue.newTimestamp64(now.minus(3L, ChronoUnit.HOURS)),
                                "c", PrimitiveValue.newDate32(now.minus(3L, ChronoUnit.DAYS).atZone(ZoneId.systemDefault()).toLocalDate()))
                )));

        Result<QueryInfo> result = tx.createQuery(insertA, paramsA).execute().join();
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        LOG.info("Statement 1 successful, transaction id {}", tx.getId());

        final String select1 = "SELECT a, b, c FROM `ts64-test/table-a` ORDER BY a LIMIT 10;";
        Result<QueryReader> output = QueryReader.readFrom(
                tx.createQueryWithCommit(select1))
                .join();
        if (! output.isSuccess()) {
            return output.getStatus();
        }

        LOG.info("Statement 2 successful, transaction committed");

        ResultSetReader rs = output.getValue().getResultSet(0);
        while (rs.next()) {
            int a = rs.getColumn(1).getInt32();
            Instant b = rs.getColumn(2).getTimestamp64();
            LocalDate c = rs.getColumn(3).getDate32();
            LOG.info("row: {}\t{}\t{}", a, b, c);
        }

        return Status.SUCCESS;
    }

    public static void main(String[] args) {
        LOG.info("YDB TS64 Transaction Example");
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
