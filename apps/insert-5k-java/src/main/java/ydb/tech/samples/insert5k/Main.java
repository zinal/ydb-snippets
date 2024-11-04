package ydb.tech.samples.insert5k;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.query.QueryTransaction;
import tech.ydb.query.result.QueryInfo;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.scheme.SchemeClient;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.ListType;
import tech.ydb.table.values.OptionalType;
import tech.ydb.table.values.OptionalValue;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructType;
import tech.ydb.table.values.StructValue;
import tech.ydb.table.values.Type;
import tech.ydb.table.values.Value;

/**
 *
 * @author mzinal
 */
public class Main implements Runnable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(Main.class);

    private static final String SYMBOLS = "0123456789"
            + "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            + "abcdefghijklmnopqrstuvwxyz"
            + "+-*/=$#!,:{}()[]"
            + "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
            + "абвгдеёжзийклмнопрстуфхцчшщъыьэюя";

    private final YdbConnector connector;
    private final AtomicInteger taskCounter = new AtomicInteger(0);

    private final TableInfo[] tableInfo = {
        new TableInfo("table-a", 80, 15),
        new TableInfo("table-b", 50, 10),
        new TableInfo("table-c", 20, 3),
        new TableInfo("table-d", 60, 5),
        new TableInfo("table-e", 10, 2),
    };
    private final TableInfo commitStats = new TableInfo("", 1, 0);

    private final AtomicLong numTotal = new AtomicLong(0);
    private final AtomicLong numFail = new AtomicLong(0);
    private final AtomicLong numEnter = new AtomicLong(0);

    private int propNumThreads = -1;
    private int propBatchSize = -1;
    private int propRunSeconds = -1;

    public Main(YdbConnector connector) {
        this.connector = connector;
    }

    private SessionRetryContext getRetryCtx() {
        return connector.getRetryCtx();
    }

    private SchemeClient getSchemeClient() {
        return connector.getSchemeClient();
    }

    private int getNumThreads() {
        return propNumThreads;
    }

    private int getBatchSize() {
        return propBatchSize;
    }

    private int getRunSeconds() {
        return propRunSeconds;
    }

    private int parseIntProperty(String name, int defval) {
        String s = connector.getConfig().getProperties().getProperty(name, String.valueOf(defval));
        int v;
        try {
            v = Integer.parseInt(s);
        } catch(NumberFormatException nfe) {
            LOG.warn("Illegal format for property '{}', default value of {} will be used", name, defval, nfe);
            v = -1;
        }
        if (v<=0) {
            v = defval;
        }
        return v;
    }

    private void parseProperties() {
        propNumThreads = parseIntProperty("numThreads", 10);
        propBatchSize = parseIntProperty("batchSize", 1000);
        propRunSeconds = parseIntProperty("runSeconds", 600);
    }

    @Override
    public void run() {
        parseProperties();
        createTables();
        runTasks();
        dropTables();
    }

    private void runDdl(String statement) {
        getRetryCtx().supplyResult(session
                -> session.createQuery(statement, TxMode.NONE).execute())
                .join().getStatus().expectSuccess();
    }

    private void createTables() {
        for (TableInfo ts : tableInfo) {
            runDdl(ts.makeTableDdl());
        }
        LOG.info("Tables created.");
    }

    private void dropTables() {
        for (TableInfo ts : tableInfo) {
            runDdl("DROP TABLE `example-insert5k/" + ts.name + "`");
        }
        LOG.info("Tables dropped.");
        getSchemeClient().removeDirectory("example-insert5k");
        LOG.info("Directory removed.");
    }

    private void runTasks() {
        ExecutorService es = Executors.newFixedThreadPool(getNumThreads());
        long tvStart = System.currentTimeMillis();
        while (true) {
            while (taskCounter.get() < 1 + getNumThreads()) {
                taskCounter.incrementAndGet();
                es.submit(() -> insertTransaction());
            }
            try {
                Thread.sleep(50L);
            } catch(InterruptedException ix) {}
            long tvFinish = System.currentTimeMillis();
            if ((tvFinish - tvStart) >= 1000L * ((long)getRunSeconds())) {
                break;
            }
        }
        try {
            es.awaitTermination(1L, TimeUnit.DAYS);
        } catch(InterruptedException ix) {}
        es.shutdownNow();
    }

    private Status insertTransaction() {
        Status status = getRetryCtx().supplyStatus(session ->
                session.beginTransaction(TxMode.SERIALIZABLE_RW)
                    .thenApply(r -> insertBody(r.getValue())))
                .join();
        numTotal.incrementAndGet();
        if (! status.isSuccess()) {
            numFail.incrementAndGet();
            LOG.warn("Transaction failed with {}", status);
        }
        taskCounter.decrementAndGet();
        return status;
    }

    private Status insertBody(QueryTransaction tx) {
        numEnter.incrementAndGet();

        long tvStart = System.currentTimeMillis();
        long tvCur, tvPrev = tvStart;

        for (TableInfo ts : tableInfo) {
            // Query execution
            String sql = ts.makeInsertStatement();
            Params params = ts.makeParams(ts, getBatchSize());
            Result<QueryInfo> result = tx.createQuery(sql, params).execute().join();
            // Statistics
            tvCur = System.currentTimeMillis();
            tvPrev = reportTime(tvCur, tvPrev, result.isSuccess(), ts);
            // Error reporting
            if (! result.isSuccess()) {
                return result.getStatus();
            }
        }

        // Commit execution
        Result<QueryInfo> result = tx.commit().join();
        // Statistics
        tvCur = System.currentTimeMillis();
        reportTime(tvCur, tvPrev, result.isSuccess(), commitStats);
        // Error reporting
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        return Status.SUCCESS;
    }

    private long reportTime(long tvCur, long tvPrev, boolean success, TableInfo ts) {
        long diff = tvCur - tvPrev;
        ts.maxTime.updateAndGet((v) -> (v > diff) ? v : diff);
        ts.sumTime.addAndGet(diff);
        ts.numTotal.incrementAndGet();
        if (! success) {
            ts.numFail.incrementAndGet();
        }
        return tvCur;
    }

    private static String formatUuid(UUID uuid) {
        ByteBuffer bb = ByteBuffer.allocate(16);
        bb.putLong(uuid.getMostSignificantBits());
        bb.putLong(uuid.getLeastSignificantBits());
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bb.array());
    }

    private static String randomString(int minLen, int maxLen) {
        ThreadLocalRandom r = ThreadLocalRandom.current();
        int len = r.nextInt(minLen, maxLen+1);
        final StringBuilder sb = new StringBuilder(len);
        while (len > 0) {
            sb.append(SYMBOLS.charAt(r.nextInt(SYMBOLS.length())));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        LOG.info("YDB Insert 5K Example");
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

    static final class TableInfo {
        final String name;
        final int columns;
        final int indexes;

        final AtomicLong maxTime = new AtomicLong(0L);
        final AtomicLong sumTime = new AtomicLong(0L);
        final AtomicLong numTotal = new AtomicLong(0L);
        final AtomicLong numFail = new AtomicLong(0L);

        TableInfo(String name, int columns, int indexes) {
            this.name = name;
            if (columns < 1) {
                columns = 1;
            }
            if (indexes < 0) {
                indexes = 0;
            }
            if (indexes > columns) {
                indexes = columns;
            }
            this.columns = columns;
            this.indexes = indexes;
        }

        String makeTableDdl() {
            StringBuilder sb = new StringBuilder();
            sb.append("CREATE TABLE `example-insert5k/").append(name).append("` (");
            sb.append("id Text NOT NULL, ");
            for (int i=0; i<columns; ++i) {
                String type = ((i%2)==0) ? "Text" : "Int64";
                sb.append("c").append(i).append(" ").append(type).append(", ");
            }
            for (int i=0; i<indexes; ++i) {
                sb.append("INDEX ix").append(i)
                        .append(" GLOBAL ON (").append("c").append(i).append("), ");
            }
            sb.append("PRIMARY KEY (id))");
            return sb.toString();
        }

        private String collectName(int num) {
            if (num >=0 && num < columns) {
                return "c" + String.valueOf(num);
            } else {
                return "id";
            }
        }

        private Type collectType(int num) {
            if (num >=0 && num < columns) {
                return OptionalType.of(((num%2)==0) ? PrimitiveType.Text : PrimitiveType.Int64);
            } else {
                return PrimitiveType.Text;
            }
        }

        private Value<?> collectValue(int num) {
            if (num >=0 && num < columns) {
                if (num >= indexes
                        && ThreadLocalRandom.current().nextInt(100) < 30) {
                    // Для неиндексируемых колонок генерируем долю NULL-значений
                    Type t;
                    if ( (num%2)==0 ) {
                        t = PrimitiveType.Text;
                    } else {
                        t = PrimitiveType.Int64;
                    }
                    return t.makeOptional().emptyValue();
                } else {
                    Value<?> v;
                    if ( (num%2)==0 ) {
                        v = PrimitiveValue.newText(randomString(0, 30));
                    } else {
                        v = PrimitiveValue.newInt64(ThreadLocalRandom.current().nextLong(1000000L));
                    }
                    return OptionalValue.of(v);
                }
            } else {
                return PrimitiveValue.newText(formatUuid(UUID.randomUUID()));
            }
        }

        private StructType makeParamType() {
            Map<String, Type> m = Stream.iterate(0, i -> i).limit(columns + 1)
                    .collect(Collectors.toMap(
                            num -> collectName(num),
                            num -> collectType(num)));
            return StructType.of(m);
        }

        private StructValue makeParamValue(StructType st) {
            Map<String, Value<?>> m = Stream.iterate(0, i -> i).limit(columns + 1)
                    .collect(Collectors.toMap(
                            num -> collectName(num),
                            num -> collectValue(num)));
            return StructValue.of(m);
        }

        private List<Value<?>> makeParamValues(StructType st, int batchSize) {
            final List<Value<?>> retval = new ArrayList<>(batchSize);
            for (int i=0; i<batchSize; ++i) {
                retval.add(makeParamValue(st));
            }
            return retval;
        }

        private Params makeParams(TableInfo ts, int batchSize) {
            StructType st = makeParamType();
            return Params.of("$input", ListType.of(st).newValue(makeParamValues(st, batchSize)));
        }

        private String makeInsertStatement() {
            return "INSERT INTO `example-insert5k/" + name + "` SELECT * FROM AS_TABLE($input);";
        }

    }

}
