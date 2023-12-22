package tech.ydb.samples.interactive.tx;

import java.util.Arrays;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.table.SessionRetryContext;
import tech.ydb.table.query.DataQueryResult;
import tech.ydb.table.query.Params;
import tech.ydb.table.transaction.TxControl;
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

    private final YdbConnector yc;
    private final SessionRetryContext rtx;

    public InteractiveTx(YdbConnector yc) {
        this.yc = yc;
        this.rtx = yc.getRetryCtx();
    }

    @Override
    public void run() {
        createTables();
        interactiveTransaction();
        dropTables();
    }

    private void createTables() {
        rtx.supplyStatus(session -> session.executeSchemeQuery(""
                + "CREATE TABLE `interactive-tx/table-a`(a Int32 NOT NULL, "
                + "  b Int32, c Utf8, PRIMARY KEY(a), "
                + "  INDEX ix_b GLOBAL ON (b))")).join().expectSuccess();
        rtx.supplyStatus(session -> session.executeSchemeQuery(""
                + "CREATE TABLE `interactive-tx/table-b`(b Int32 NOT NULL, "
                + "  c Text, PRIMARY KEY(b))")).join().expectSuccess();
        LOG.info("Tables created.");
    }

    private void dropTables() {
        rtx.supplyStatus(session -> session.executeSchemeQuery(""
                + "DROP TABLE `interactive-tx/table-a`")).join().expectSuccess();
        rtx.supplyStatus(session -> session.executeSchemeQuery(""
                + "DROP TABLE `interactive-tx/table-b`")).join().expectSuccess();
        LOG.info("Tables dropped.");
        yc.getSchemeClient().removeDirectory("interactive-tx");
        LOG.info("Directory removed.");
    }

    private void interactiveTransaction() {
        LOG.info("Start of interactive transaction");
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
        Result<DataQueryResult> dqr = rtx.supplyResult(session -> session.executeDataQuery(insertA,
                TxControl.serializableRw().setCommitTx(false), paramsA)).join();
        dqr.getStatus().expectSuccess();

        LOG.info("Statement 1 successful, transaction id {}", dqr.getValue().getTxId());

        final TxControl<?> txc = TxControl.id(dqr.getValue().getTxId());
        

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
        dqr = rtx.supplyResult(session -> session.executeDataQuery(insertB,
                txc.setCommitTx(true), paramsB)).join();
        dqr.getStatus().expectSuccess();

        LOG.info("Statement 2 successful, transaction committed");
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
