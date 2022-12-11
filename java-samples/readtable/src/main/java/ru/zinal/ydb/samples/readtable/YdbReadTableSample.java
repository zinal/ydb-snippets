package ru.zinal.ydb.samples.readtable;

import java.io.File;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.apache.commons.io.FileUtils;
import tech.ydb.core.Status;
import tech.ydb.core.auth.AuthProvider;
import tech.ydb.core.auth.StaticCredentials;
import tech.ydb.core.grpc.GrpcTransport;
import tech.ydb.core.grpc.GrpcTransportBuilder;
import tech.ydb.table.SessionRetryContext;
import tech.ydb.table.TableClient;
import tech.ydb.table.settings.BulkUpsertSettings;
import tech.ydb.table.values.ListType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.Value;
import tech.ydb.auth.iam.CloudAuthHelper;
import tech.ydb.table.Session;
import tech.ydb.table.settings.ReadTableSettings;
import tech.ydb.table.values.ListValue;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.StructType;
import tech.ydb.table.values.TupleValue;

/**
 *
 * @author mzinal
 */
public class YdbReadTableSample implements AutoCloseable {

    private static final org.slf4j.Logger LOG =
            org.slf4j.LoggerFactory.getLogger(YdbReadTableSample.class);

    private final GrpcTransport transport;
    private final TableClient tableClient;
    private final SessionRetryContext retryCtx;
    private final String database;

    /**
     * The constructor opens the connection to YDB.
     * Authentication parameters should be passed via the environment variables.
     * @param connection Connection string, combining the endpoint and database
     * @throws Exception
     */
    public YdbReadTableSample(String connection) throws Exception {
        GrpcTransportBuilder builder = GrpcTransport
                .forConnectionString(connection);
        String staticCredsFile = System.getenv("YDB_STATIC_CREDS_FILE");
        if (staticCredsFile == null)
            staticCredsFile = "";
        else
            staticCredsFile = staticCredsFile.trim();
        if (staticCredsFile.length() > 0) {
            builder = builder.withAuthProvider(readStaticCreds(staticCredsFile));
        } else {
            builder = builder.withAuthProvider(
                    CloudAuthHelper.getAuthProviderFromEnviron());
        }
        GrpcTransport transport = builder.build();
        this.database = transport.getDatabase();
        try {
            this.tableClient = TableClient.newClient(transport)
                    .sessionMaxIdleTime(Duration.ofSeconds(60))
                    .sessionPoolSize(0, 10)
                    .build();
            this.retryCtx = SessionRetryContext.create(tableClient)
                    .sessionCreationTimeout(Duration.ofSeconds(10)).build();
            this.transport = transport;
            transport = null; // to avoid closing below
        } finally {
            if (transport != null)
                transport.close();
        }
    }

    /**
     * Closing the connections to YDB.
     * In addition to TableClient, GrpcTransport object must be closed
     * explicitly, to avoid the resource leaks and to terminate
     * the utility threads.
     */
    @Override
    public void close() {
        if (tableClient != null) {
            try {
                tableClient.close();
            } catch(Exception ex) {
                LOG.warn("TableClient closing threw an exception", ex);
            }
        }
        if (transport != null) {
            try {
                transport.close();
            } catch(Exception ex) {
                LOG.warn("GrpcTransport closing threw an exception", ex);
            }
        }
    }

    public String getDatabase() {
        return database;
    }

    /**
     * Top-level logic of the sample, which creates the table, pushes some data into it,
     * and performs a table scan with the filter on PK values after that.
     * @throws Exception
     */
    public void run() throws Exception {
        createTable();
        upsertData();
        grabRecords();
    }

    /**
     * Creating the table with compound key using YQL statement.
     * @throws Exception
     */
    public void createTable() throws Exception {
        LOG.info("createTable() started");
        final String tableYql = "CREATE TABLE readtable_demo("
                + "A Int32 NOT NULL,"
                + "B Int32 NOT NULL,"
                + "C Int32 NOT NULL,"
                + "D Utf8,"
                + "E Utf8,"
                + "PRIMARY KEY(A,B,C))";
        retryCtx.supplyStatus(
                session -> session.executeSchemeQuery(tableYql)
        ).join().expectSuccess();
        LOG.info("createTable() completed");
    }

    /**
     * Generating and upserting the data to the table.
     * Async operations are used, so the data continues to be generated
     * while the previous portion is being upserted.
     * In this simple implementation, only one async operation can be running.
     * @throws Exception
     */
    public void upsertData() throws Exception {
        LOG.info("upsertData() started");

        final String tablePath = database + "/" + "readtable_demo";

        final StructType rowType = StructType.of(
                "A", PrimitiveType.Int32,
                "B", PrimitiveType.Int32,
                "C", PrimitiveType.Int32,
                "D", PrimitiveType.Text,
                "E", PrimitiveType.Text);
        final ListType listType = ListType.of(rowType);

        final int maxRows = 10000;
        List<Value<?>> batch = new ArrayList<>(maxRows);
        final UpsertHelper helper = new UpsertHelper(retryCtx, new BulkUpsertSettings());
        
        for (int c=0; c<10000; ++c) {
            for (int b=0; b<10; ++b) {
                for (int a=0; a<10; ++a) {
                    String d = String.valueOf(a)
                            + "/" + String.valueOf(b)
                            + "/" + String.valueOf(c);
                    String e = UUID.randomUUID().toString();
                    batch.add(rowType.newValue(
                            "A", PrimitiveValue.newInt32(a),
                            "B", PrimitiveValue.newInt32(b),
                            "C", PrimitiveValue.newInt32(c),
                            "D", PrimitiveValue.newText(d),
                            "E", PrimitiveValue.newText(e)));
                    if (batch.size() >= maxRows) {
                        helper.addList(tablePath, batch, listType);
                        batch.clear();
                    }
                }
            }
        }

        if (! batch.isEmpty()) {
            helper.addList(tablePath, batch, listType);
        }
        helper.finish();

        LOG.info("upsertData() completed");
    }

    public void grabRecords() throws Exception {
        LOG.info("grabRecords() started");

        final Value A_VAL = PrimitiveValue.newInt32(5).makeOptional();
        final Value B_VAL = PrimitiveValue.newInt32(3).makeOptional();

        final String tablePath = database + "/" + "readtable_demo";
        final ReadTableSettings settings = ReadTableSettings.newBuilder()
                .columns("A", "B", "C", "D", "E")
                .fromKeyInclusive(TupleValue.of(A_VAL, B_VAL))
                .toKeyInclusive(TupleValue.of(A_VAL, B_VAL))
                .timeout(Duration.ofHours(8))
                .build();

        try (Session session = tableClient.createSession(Duration.ofSeconds(10)).join().getValue()) {
            session.readTable(tablePath, settings, rs -> {
                LOG.info("*** next portion, size={}", rs.getRowCount());
                int ca = rs.getColumnIndex("A");
                int cb = rs.getColumnIndex("B");
                int cc = rs.getColumnIndex("C");
                int cd = rs.getColumnIndex("D");
                int ce = rs.getColumnIndex("E");
                while (rs.next()) {
                    LOG.info("\tA={}, B={}, C={}, D={}, E={}",
                            rs.getColumn(ca).getInt32(),
                            rs.getColumn(cb).getInt32(),
                            rs.getColumn(cc).getInt32(),
                            rs.getColumn(cd).getText(),
                            rs.getColumn(ce).getText());
                }
            }).join().expectSuccess();
        }

        LOG.info("grabRecords() completed");
    }

    /**
     * Application entry point
     * @param args
     */
    public static void main(String[] args) {
        if (args.length != 1) {
            System.out.println("USAGE: YdbReadTableSample CONNECTION");
            System.exit(2);
        }
        try (YdbReadTableSample sample = new YdbReadTableSample(args[0])) {
            sample.run();
        } catch(Exception ex) {
            LOG.error("FATAL", ex);
            System.exit(1);
        }
    }

    /**
     * Helper function to read username and password from the file.
     * @param f File name
     * @return StaticCredentials object containing the username and password
     * @throws Exception
     */
    public static AuthProvider readStaticCreds(String f) throws Exception {
        String data = FileUtils.readFileToString(new File(f), StandardCharsets.UTF_8);
        int pos = data.indexOf(':');
        if (pos < 0)
            return new StaticCredentials(data, "");
        return new StaticCredentials(data.substring(0, pos), data.substring(pos+1));
    }

    /**
     * Helper class to simplify the asynchronous records upsertion.
     */
    private static class UpsertHelper {
        private final SessionRetryContext retryCtx;
        private final BulkUpsertSettings upsertSettings;
        private CompletableFuture<Status> status = null;

        public UpsertHelper(SessionRetryContext retryCtx, BulkUpsertSettings upsertSettings) {
            this.retryCtx = retryCtx;
            this.upsertSettings = upsertSettings;
        }

        /**
         * Complete the current async operaion, if one is present.
         */
        public void finish() {
            if (status == null)
                return;
            status.join().expectSuccess();
            status = null;
        }

        /**
         * Start the new async operation to upsert the additional list of rows to the table.
         * The previously running async operation will be finished and checked for errors.
         * @param tablePath Full path to table
         * @param newValue List of records to be upserted
         */
        public void add(String tablePath, ListValue newValue) {
            if (newValue==null || newValue.isEmpty())
                return;
            finish();
            status = retryCtx.supplyStatus(
                    session -> session.executeBulkUpsert(tablePath, newValue, upsertSettings)
            );
        }

        /**
         * Start the new async operation to upsert the additional list of rows to the table.
         * The previously running async operation will be finished and checked for errors.
         * @param tablePath Full path to table
         * @param batch List of records to be upserted
         * @param listType YDB list type
         */
        public void addList(String tablePath, List<Value<?>> batch, ListType listType) {
            if (batch==null || batch.isEmpty())
                return;
            add(tablePath, listType.newValue(batch));
        }
    }

}
