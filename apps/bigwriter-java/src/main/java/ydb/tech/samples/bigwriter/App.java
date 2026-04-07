package ydb.tech.samples.bigwriter;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ThreadLocalRandom;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Status;
import tech.ydb.query.QuerySession;
import tech.ydb.query.QueryTransaction;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.PrimitiveValue;

/**
 * CREATE TABLE bigtab(a Int32, b Text, PRIMARY KEY(a))
 *
 * @author mzinal
 */
public class App implements Runnable, AutoCloseable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(App.class);
    private static final String CHARS = "abcdefgjigklmnopqrstuvwxyzABCDEFJHIGKLMNOPQRSTUVWXYZ";

    private final YdbConnector yc;

    public App(String configFile) {
        this.yc = new YdbConnector(configFile);
    }

    @Override
    public void close() {
        yc.close();
    }

    @Override
    public void run() {
        LOG.info("Starting...");
        yc.getQueryRetryCtx().supplyStatus(qs -> insertMany(qs))
                .join().expectSuccess();
        LOG.info("Completed!");
    }

    private CompletableFuture<Status> insertMany(QuerySession qs) {
        var trans = qs.createNewTransaction(TxMode.SERIALIZABLE_RW);
        int amount = 0;
        final int limit = 128 * 1024 * 1024;
        LOG.info("Inserting...");
        while (amount < limit) {
            int step = insertSingle(amount, trans);
            amount += step;
            LOG.info("Step {}, total {}", step, amount);
        }
        return trans.commit().thenApply(res -> res.getStatus());
    }

    private int insertSingle(int position, QueryTransaction trans) {
        var p_b = makeString(ThreadLocalRandom.current().nextInt(500, 900));
        trans.createQuery("UPSERT INTO bigtab(a,b) VALUES($a, $b)",
                Params.of("$a", PrimitiveValue.newInt32(position),
                        "$b", PrimitiveValue.newText(p_b)))
                .execute().thenApply(res -> res.getStatus())
                .join().expectSuccess();
        return p_b.length();
    }

    private String makeString(int length) {
        var random = ThreadLocalRandom.current();
        var sb = new StringBuilder(length);
        for (int i = 0; i < length; ++i) {
            int ix = random.nextInt(0, CHARS.length() - 1);
            sb.append(CHARS.substring(ix, ix + 1));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        if (args.length != 1) {
            System.out.println("USAGE: App connect.xml");
            System.exit(2);
        }
        try {
            try (App app = new App(args[0])) {
                app.run();
            }
        } catch (Exception ex) {
            LOG.error("FATAL", ex);
            System.exit(1);
        }
    }
}
