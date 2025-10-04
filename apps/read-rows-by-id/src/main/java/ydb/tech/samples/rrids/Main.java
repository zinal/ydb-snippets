package ydb.tech.samples.rrids;

import com.google.common.collect.Lists;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Random;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.query.QueryTransaction;
import tech.ydb.query.tools.QueryReader;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.ListValue;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.Value;

/**
 *
 * @author mzinal
 */
public class Main implements Runnable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(Main.class);

    private final YdbConnector connector;
    private final Random random;

    public Main(YdbConnector connector) {
        this.connector = connector;
        this.random = new Random();
    }

    private SessionRetryContext getRetryCtx() {
        return connector.getRetryCtx();
    }

    @Override
    public void run() {
        List<Value<?>> ids = loadIds();
        LOG.info("Loaded ids, total of {}", ids.size());
        final int rounds = 100;
        final int portionSize = 50000;
        LOG.info("Running simple test...");
        final long tvStart1 = System.currentTimeMillis();
        for (int i = 0; i < rounds; ++i) {
            List<Value<?>> portion = makePortion(portionSize, ids);
            simpleSelect(portion);
        }
        LOG.info("Running optimized test...");
        final long tvFinish1 = System.currentTimeMillis();
        for (int i = 0; i < rounds; ++i) {
            List<Value<?>> portion = makePortion(portionSize, ids);
            optimizedSelect(portion);
        }
        final long tvFinish2 = System.currentTimeMillis();
        LOG.info("Simple time: {}", (tvFinish1 - tvStart1));
        LOG.info("Optimized time: {}", (tvFinish2 - tvFinish1));
    }

    private List<Value<?>> loadIds() {
        try {
            return new ArrayList<>(
                    Files.lines(Path.of("bank_document_ids.txt"))
                            .map(s -> unquote(s))
                            .filter(s -> s.length() > 0)
                            .map(s -> PrimitiveValue.newText(s))
                            .toList()
            );
        } catch (Exception ex) {
            throw new RuntimeException("Cannot load input file", ex);
        }
    }

    private String unquote(String v) {
        if (v == null) {
            return "";
        }
        if (v.startsWith("\"") && v.endsWith("\"")) {
            return v.substring(1, v.length() - 1);
        }
        return v;
    }

    private List<Value<?>> makePortion(int portionSize, List<Value<?>> ids) {
        List<Value<?>> portion = new ArrayList<>(portionSize);
        var used = new HashSet<Integer>(2 * portionSize);
        for (int i = 0; i < portionSize; ++i) {
            int index;
            do {
                index = random.nextInt(0, ids.size());
            } while (!used.add(index));
            portion.add(ids.get(index));
        }
        return portion;
    }

    private void simpleSelect(List<Value<?>> portion) {
        getRetryCtx().supplyStatus(session
                -> session.beginTransaction(TxMode.SERIALIZABLE_RW)
                        .thenApply(r -> simpleBody(r.getValue(), portion)))
                .join().expectSuccess();
    }

    private void optimizedSelect(List<Value<?>> portion) {
        getRetryCtx().supplyStatus(session
                -> session.beginTransaction(TxMode.SERIALIZABLE_RW)
                        .thenApply(r -> optimizedBody(r.getValue(), portion)))
                .join().expectSuccess();
    }

    private Status runSelect(QueryTransaction tx, List<Value<?>> portion) {
        final String statement = "DECLARE $ids AS List<String>; "
                + "SELECT * FROM `work0/bank_document` WHERE id IN $ids;";
        Params params = Params.of("$ids", ListValue.of(portion.toArray(Value<?>[]::new)));
        Result<QueryReader> output = QueryReader.readFrom(
                tx.createQuery(statement, params))
                .join();
        return output.getStatus();
    }

    private Status simpleBody(QueryTransaction tx, List<Value<?>> portion) {
        // unsorted, part size is 10k
        for (var part : Lists.partition(portion, 10000)) {
            var status = runSelect(tx, part);
            if (!status.isSuccess()) {
                return status;
            }
        }
        return tx.commit().join().getStatus();
    }

    private Status optimizedBody(QueryTransaction tx, List<Value<?>> portion) {
        // sorted, part size is 1k
        portion.sort((a, b) -> a.asData().getText().compareTo(b.asData().getText()));
        for (var part : Lists.partition(portion, 1000)) {
            var status = runSelect(tx, part);
            if (!status.isSuccess()) {
                return status;
            }
        }
        return tx.commit().join().getStatus();
    }

    public static void main(String[] args) {
        LOG.info("YDB Select-By-Id Example");
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
