package ydb.tech.samples.insert5k;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import tech.ydb.common.transaction.TxMode;
import tech.ydb.core.Result;
import tech.ydb.core.Status;
import tech.ydb.core.StatusCode;
import tech.ydb.query.QuerySession;
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

    private static final ThreadLocal<String> EXEC_STEP = new ThreadLocal<>();

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
    private final AtomicLong timeSuccess = new AtomicLong(0);
    private final AtomicLong timeFail = new AtomicLong(0);

    private int propNumThreads = -1;
    private int propBatchSize = -1;
    private int propRunSeconds = -1;
    private boolean propEnableCreate = false;
    private boolean propEnableDrop = false;

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

    private boolean isCreateEnabled() {
        return propEnableCreate;
    }

    private boolean isDropEnabled() {
        return propEnableDrop;
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

    private boolean parseBoolProperty(String name, boolean defval) {
        String s = connector.getConfig().getProperties().getProperty(name, String.valueOf(defval));
        return Boolean.parseBoolean(s);
    }

    private void parseProperties() {
        propNumThreads = parseIntProperty("numThreads", 10);
        propBatchSize = parseIntProperty("batchSize", 1000);
        propRunSeconds = parseIntProperty("runSeconds", 600);
        propEnableCreate = parseBoolProperty("enableCreate", true);
        propEnableDrop = parseBoolProperty("enableDrop", false);
    }

    @Override
    public void run() {
        parseProperties();
        createTables();
        runTasks();
        printResults();
        dropTables();
    }

    private void runDdl(String statement) {
        getRetryCtx().supplyResult(session
                -> session.createQuery(statement, TxMode.NONE).execute())
                .join().getStatus().expectSuccess();
    }

    private void createTables() {
        if (! isCreateEnabled()) {
            LOG.info("Tables creation skipped.");
            return;
        }
        LOG.info("Tables creation started.");
        for (TableInfo ts : tableInfo) {
            runDdl(ts.makeTableDdl());
            LOG.info("\tCreated table: {}", ts.name);
        }
        LOG.info("Tables created.");
    }

    private void dropTables() {
        if (! isDropEnabled()) {
            LOG.info("Tables dropping skipped.");
            return;
        }
        LOG.info("Tables dropping started.");
        for (TableInfo ts : tableInfo) {
            runDdl("DROP TABLE `example-insert5k/" + ts.name + "`");
            LOG.info("\tDropped table: {}", ts.name);
        }
        LOG.info("Tables dropped.");
        getSchemeClient().removeDirectory("example-insert5k");
        LOG.info("Directory removed.");
    }

    private void runTasks() {
        LOG.info("Running tasks in {} thread(s).", getNumThreads());
        ExecutorService es = Executors.newFixedThreadPool(getNumThreads());
        long tvStart = System.currentTimeMillis();
        long lastReported = 0L;
        while (true) {
            while (taskCounter.get() < 1 + getNumThreads()) {
                taskCounter.incrementAndGet();
                es.submit(() -> taskBody());
            }
            sleepSome();
            long tvFinish = System.currentTimeMillis();
            long diff = tvFinish - tvStart;
            if (diff >= 1000L * ((long)getRunSeconds())) {
                break;
            }
            if (diff - lastReported >= 10000L) {
                printProgress();
                lastReported = diff;
            }
        }
        printProgress();
        LOG.info("Timer reached, waiting for remaining {} task(s) to complete...", 
                taskCounter.get());
        while ( taskCounter.get() > 0L ) {
            sleepSome();
        }
        es.shutdownNow();
    }
    
    private void sleepSome() {
        try {
            Thread.sleep(73L);
        } catch(InterruptedException ix) {}
    }

    private Status taskBody() {
        // Генерируем порцию данных для последующей вставки
        final TaskInput input = new TaskInput();
        long tvStart = System.currentTimeMillis();
        Status status;
        try {
            status = getRetryCtx().supplyStatus(session -> transactionAsync(session, input)).join();
        } catch(Throwable ex) {
            LOG.info("Unexpected exception on transaction {} execution", input.inputId, ex);
            status = Status.of(StatusCode.CLIENT_INTERNAL_ERROR, ex);
        }
        long tvDiff = System.currentTimeMillis() - tvStart;
        numTotal.incrementAndGet();
        if (status.isSuccess()) {
            timeSuccess.addAndGet(tvDiff);
        } else {
            numFail.incrementAndGet();
            timeFail.addAndGet(tvDiff);
            LOG.warn("Transaction {} finally failed with {}", input.inputId, status);
        }
        taskCounter.decrementAndGet();
        return status;
    }

    private CompletableFuture<Status> transactionAsync(QuerySession session, TaskInput input) {
        EXEC_STEP.set("ENTRY");
        Status status;
        try {
            status = transactionBody(session, input);
        } catch(Throwable ex) {
            status = Status.of(StatusCode.CLIENT_INTERNAL_ERROR, ex);
        }
        if (! status.isSuccess()) {
            LOG.warn("Transaction {} preliminarily failed on step {} with {}",
                    input.inputId, EXEC_STEP.get(), status);
        }
        return CompletableFuture.completedFuture(status);
    }

    private Status transactionBody(QuerySession session, TaskInput input) {
        numEnter.incrementAndGet();
        EXEC_STEP.set("BODY");

        long tvStart = System.currentTimeMillis();
        long tvCur, tvPrev = tvStart;

        QueryTransaction tx = session.createNewTransaction(TxMode.SERIALIZABLE_RW);

        EXEC_STEP.set("TX");

        for (int i=0; i<tableInfo.length; ++i) {
            EXEC_STEP.set("TABLE:" + tableInfo[i].name);
            // Query execution
            String sql = tableInfo[i].insertOperator;
            Params params = input.params[i];
            Result<QueryInfo> result = tx.createQuery(sql, params).execute().join();
            // Statistics
            tvCur = System.currentTimeMillis();
            tvPrev = reportTime(tvCur, tvPrev, result.isSuccess(), tableInfo[i]);
            // Error reporting
            if (! result.isSuccess()) {
                return result.getStatus();
            }
        }

        EXEC_STEP.set("COMMIT");

        // Commit execution
        Result<QueryInfo> result = tx.commit().join();

        // Statistics
        tvCur = System.currentTimeMillis();
        reportTime(tvCur, tvPrev, result.isSuccess(), commitStats);
        // Error reporting
        if (! result.isSuccess()) {
            return result.getStatus();
        }

        EXEC_STEP.set("SUCCESS");

        return Status.SUCCESS;
    }

    private void printProgress() {
        LOG.info("Progress: {} completed transactions, including {} failures.",
                numTotal.get(), numFail.get());
    }

    private void printResults() {
        LOG.info("Total {} transactions, including {} failures.", numTotal.get(), numFail.get());
        LOG.info("Transaction retries: {} total, average rate {}",
                numEnter.get() - numTotal.get(), formatRetryRate());
        LOG.info("Average success time, msec: {} (including retries)",
                timeSuccess.get() / (numTotal.get() - numFail.get()));
        LOG.info("Average failure time, msec: {} (including retries)",
                timeFail.get() / (numTotal.get() - numFail.get()));
        printStats("COMMIT", commitStats);
        for (TableInfo ti : tableInfo) {
            printStats(ti.name, ti);
        }
    }

    private void printStats(String name, TableInfo ti) {
        LOG.info("*** {} statistics", name);
        LOG.info("*** \tCounts: {} total, {} failed", ti.numTotal.get(), ti.numFail.get());
        LOG.info("*** \tTiming: {} max, {} avg (msec)", ti.maxTime.get(),
                ti.sumTime.get() / ti.numTotal.get());
    }

    private String formatRetryRate() {
        double retries = numEnter.get() - numTotal.get();
        double trans = numTotal.get();
        return String.format("%1.2f", 100.0 * retries / trans) + "%";
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
        while (len-- > 0) {
            sb.append(SYMBOLS.charAt(r.nextInt(SYMBOLS.length())));
        }
        return sb.toString();
    }

    private static void addShardingOptions(StringBuilder sb) {
        sb.append("WITH (")
                .append("AUTO_PARTITIONING_BY_LOAD = ENABLED,")
                .append("AUTO_PARTITIONING_BY_SIZE = ENABLED,")
                .append("AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 800,")
                .append("AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 1000,")
                .append("PARTITION_AT_KEYS = (");
        sb.append("'-4','-A','-F','-L','-R','-X','-d','-j','-p','-v','0-','04','0A','0F','0L','0R','0X','0d','0j','0p',");
        sb.append("'0v','1-','14','1A','1F','1L','1R','1X','1d','1j','1p','1v','2-','24','2A','2F','2L','2R','2X','2d',");
        sb.append("'2j','2p','2v','3-','34','3A','3F','3L','3R','3X','3d','3j','3p','3v','4-','44','4A','4F','4L','4R',");
        sb.append("'4X','4d','4j','4p','4v','5-','54','5A','5F','5L','5R','5X','5d','5j','5p','5v','6-','64','6A','6F',");
        sb.append("'6L','6R','6X','6d','6j','6p','6v','7-','74','7A','7F','7L','7R','7X','7d','7j','7p','7v','8-','84',");
        sb.append("'8A','8F','8L','8R','8X','8d','8j','8p','8v','9-','94','9A','9F','9L','9R','9X','9d','9j','9p','9v',");
        sb.append("'A-','A4','AA','AF','AL','AR','AX','Ad','Aj','Ap','Av','B-','B4','BA','BF','BL','BR','BX','Bd','Bj',");
        sb.append("'Bp','Bv','C-','C4','CA','CF','CL','CR','CX','Cd','Cj','Cp','Cv','D-','D4','DA','DF','DL','DR','DX',");
        sb.append("'Dd','Dj','Dp','Dv','E-','E4','EA','EF','EL','ER','EX','Ed','Ej','Ep','Ev','F-','F4','FA','FF','FL',");
        sb.append("'FR','FX','Fd','Fj','Fp','Fv','G-','G4','GA','GF','GL','GR','GX','Gd','Gj','Gp','Gv','H-','H4','HA',");
        sb.append("'HF','HL','HR','HX','Hd','Hj','Hp','Hv','I-','I4','IA','IF','IL','IR','IX','Id','Ij','Ip','Iv','J-',");
        sb.append("'J4','JA','JF','JL','JR','JX','Jd','Jj','Jp','Jv','K-','K4','KA','KF','KL','KR','KX','Kd','Kj','Kp',");
        sb.append("'Kv','L-','L4','LA','LF','LL','LR','LX','Ld','Lj','Lp','Lv','M-','M4','MA','MF','ML','MR','MX','Md',");
        sb.append("'Mj','Mp','Mv','N-','N4','NA','NF','NL','NR','NX','Nd','Nj','Np','Nv','O-','O4','OA','OF','OL','OR',");
        sb.append("'OX','Od','Oj','Op','Ov','P-','P4','PA','PF','PL','PR','PX','Pd','Pj','Pp','Pv','Q-','Q4','QA','QF',");
        sb.append("'QL','QR','QX','Qd','Qj','Qp','Qv','R-','R4','RA','RF','RL','RR','RX','Rd','Rj','Rp','Rv','S-','S4',");
        sb.append("'SA','SF','SL','SR','SX','Sd','Sj','Sp','Sv','T-','T4','TA','TF','TL','TR','TX','Td','Tj','Tp','Tv',");
        sb.append("'U-','U4','UA','UF','UL','UR','UX','Ud','Uj','Up','Uv','V-','V4','VA','VF','VL','VR','VX','Vd','Vj',");
        sb.append("'Vp','Vv','W-','W4','WA','WF','WL','WR','WX','Wd','Wj','Wp','Wv','X-','X4','XA','XF','XL','XR','XX',");
        sb.append("'Xd','Xj','Xp','Xv','Y-','Y4','YA','YF','YL','YR','YX','Yd','Yj','Yp','Yv','Z-','Z4','ZA','ZF','ZL',");
        sb.append("'ZR','ZX','Zd','Zj','Zp','Zv','_-','_4','_A','_F','_L','_R','_X','_d','_j','_p','_v','a-','a4','aA',");
        sb.append("'aF','aL','aR','aX','ad','aj','ap','av','b-','b4','bA','bF','bL','bR','bX','bd','bj','bp','bv','c-',");
        sb.append("'c4','cA','cF','cL','cR','cX','cd','cj','cp','cv','d-','d4','dA','dF','dL','dR','dX','dd','dj','dp',");
        sb.append("'dv','e-','e4','eA','eF','eL','eR','eX','ed','ej','ep','ev','f-','f4','fA','fF','fL','fR','fX','fd',");
        sb.append("'fj','fp','fv','g-','g4','gA','gF','gL','gR','gX','gd','gj','gp','gv','h-','h4','hA','hF','hL','hR',");
        sb.append("'hX','hd','hj','hp','hv','i-','i4','iA','iF','iL','iR','iX','id','ij','ip','iv','j-','j4','jA','jF',");
        sb.append("'jL','jR','jX','jd','jj','jp','jv','k-','k4','kA','kF','kL','kR','kX','kd','kj','kp','kv','l-','l4',");
        sb.append("'lA','lF','lL','lR','lX','ld','lj','lp','lv','m-','m4','mA','mF','mL','mR','mX','md','mj','mp','mv',");
        sb.append("'n-','n4','nA','nF','nL','nR','nX','nd','nj','np','nv','o-','o4','oA','oF','oL','oR','oX','od','oj',");
        sb.append("'op','ov','p-','p4','pA','pF','pL','pR','pX','pd','pj','pp','pv','q-','q4','qA','qF','qL','qR','qX',");
        sb.append("'qd','qj','qp','qv','r-','r4','rA','rF','rL','rR','rX','rd','rj','rp','rv','s-','s4','sA','sF','sL',");
        sb.append("'sR','sX','sd','sj','sp','sv','t-','t4','tA','tF','tL','tR','tX','td','tj','tp','tv','u-','u4','uA',");
        sb.append("'uF','uL','uR','uX','ud','uj','up','uv','v-','v4','vA','vF','vL','vR','vX','vd','vj','vp','vv','w-',");
        sb.append("'w4','wA','wF','wL','wR','wX','wd','wj','wp','wv','x-','x4','xA','xF','xL','xR','xX','xd','xj','xp',");
        sb.append("'xv','y-','y4','yA','yF','yL','yR','yX','yd','yj','yp','yv','z-','z4','zA','zF','zL','zR','zX','zd',");
        sb.append("'zj','zp','zv'");
        sb.append("))");
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

    final class TaskInput {
        final String inputId;
        final Params params[];

        TaskInput() {
            this.inputId = formatUuid(UUID.randomUUID());
            this.params = new Params[tableInfo.length];
            for (int i=0; i<tableInfo.length; ++i) {
                this.params[i] = tableInfo[i].makeParams(getBatchSize());
            }
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

        final String insertOperator;

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
            this.insertOperator = makeInsertStatement();
        }

        String makeTableDdl() {
            StringBuilder sb = new StringBuilder();
            sb.append("CREATE TABLE `example-insert5k/").append(name).append("` (");
            sb.append("id Text NOT NULL, ");
            for (int i=0; i<columns; ++i) {
                sb.append("c").append(i).append(" ")
                        .append(collectTypeName(i)).append(", ");
            }
            for (int i=0; i<indexes; ++i) {
                sb.append("INDEX ix").append(i)
                        .append(" GLOBAL ON (").append("c").append(i).append("), ");
            }
            sb.append("PRIMARY KEY (id)) ");
            addShardingOptions(sb);
            return sb.toString();
        }

        private String collectName(int num) {
            if (num >=0 && num < columns) {
                return "c" + String.valueOf(num);
            } else {
                return "id";
            }
        }

        private String collectTypeName(int num) {
            if (num >=0 && num < columns) {
                return ((num%2)==0) ? "Text" : "Int64";
            } else {
                return "Text";
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
            Map<String, Type> m = Stream.iterate(0, i -> i+1).limit(columns + 1)
                    .collect(Collectors.toMap(
                            num -> collectName(num),
                            num -> collectType(num)));
            return StructType.of(m);
        }

        private StructValue makeParamValue(StructType st) {
            Map<String, Value<?>> m = Stream.iterate(0, i -> i+1).limit(columns + 1)
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

        private Params makeParams(int batchSize) {
            StructType st = makeParamType();
            return Params.of("$input", ListType.of(st).newValue(makeParamValues(st, batchSize)));
        }

        private String makeInsertStatement() {
            if (name==null || name.length()==0) {
                return "";
            }
            final StringBuilder sb = new StringBuilder();
            sb.append("DECLARE $input AS List<Struct<id:Text,");
            for (int i=0; i<columns; ++i) {
                sb.append("c").append(i).append(":")
                        .append(collectTypeName(i)).append("?, ");
            }
            sb.append(">>;");
            sb.append("INSERT INTO `example-insert5k/").append(name)
                    .append("` SELECT * FROM AS_TABLE($input);");
            return  sb.toString();
        }

    }

}
