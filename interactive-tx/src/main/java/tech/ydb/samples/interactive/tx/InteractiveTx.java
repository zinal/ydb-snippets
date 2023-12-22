package tech.ydb.samples.interactive.tx;

/**
 * YDB native SDK samples - interactive read/write transaction example.
 *
 * @author mzinal
 */
public class InteractiveTx implements Runnable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(InteractiveTx.class);

    private final YdbConnector yc;

    public InteractiveTx(YdbConnector yc) {
        this.yc = yc;
    }

    @Override
    public void run() {
        createTables();
        dropTables();
    }

    private void createTables() {
        yc.getRetryCtx().supplyStatus(session -> session.executeSchemeQuery(""
                + "CREATE TABLE `interactive-tx/table-a`(a Int32 NOT NULL, "
                + "  b Int32, c Text, PRIMARY KEY(a))")).join().expectSuccess();
        yc.getRetryCtx().supplyStatus(session -> session.executeSchemeQuery(""
                + "CREATE TABLE `interactive-tx/table-b`(b Int32 NOT NULL, "
                + "  c Text, PRIMARY KEY(b))")).join().expectSuccess();
        LOG.info("Tables created.");
    }

    private void dropTables() {
        yc.getRetryCtx().supplyStatus(session -> session.executeSchemeQuery(""
                + "DROP TABLE `interactive-tx/table-a`")).join().expectSuccess();
        yc.getRetryCtx().supplyStatus(session -> session.executeSchemeQuery(""
                + "DROP TABLE `interactive-tx/table-b`")).join().expectSuccess();
        LOG.info("Tables dropped.");
        yc.getSchemeClient().removeDirectory("interactive-tx");
        LOG.info("Directory removed.");
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
