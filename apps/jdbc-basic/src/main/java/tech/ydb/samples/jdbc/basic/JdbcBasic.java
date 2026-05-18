package tech.ydb.samples.jdbc.basic;

import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import tech.ydb.common.transaction.YdbTransaction;
import tech.ydb.core.grpc.GrpcTransport;
import tech.ydb.topic.TopicClient;
import tech.ydb.topic.settings.SendSettings;
import tech.ydb.topic.settings.WriterSettings;
import tech.ydb.topic.write.Message;
import tech.ydb.topic.write.SyncWriter;

/**
 *
 * @author zinal
 */
public class JdbcBasic {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(JdbcBasic.class);
    private static final boolean NEED_DUMP_THREADS = false;

    public static void main(String[] args) {
        try (var con = getConnection()) {
            createTables(con);
            try (var pool = Executors.newCachedThreadPool()) {
                long tvStart = System.currentTimeMillis();
                for (int i = 1; i < 101; ++i) {
                    jdbcTest(i, con, pool);
                }
                long tvFinish = System.currentTimeMillis();
                LOG.info("SUCCESS!");
                long tvTotal = tvFinish - tvStart;
                LOG.info("Execution total millis: {}, per transaction: {}", tvTotal, tvTotal / 100);
                LOG.info("--");
            } finally {
                cleanup(con);
            }
        } catch (Exception ex) {
            LOG.error("FAILED!", ex);
        }
        if (NEED_DUMP_THREADS) {
            dumpThreads();
        }
    }

    private static void createTables(Connection con) throws Exception {
        con.setAutoCommit(true);
        try (var stmt = con.createStatement()) {
            stmt.execute("CREATE TABLE tab_test1(a Int32, b Text, PRIMARY KEY(a))");
            stmt.execute("CREATE TOPIC top_test1(CONSUMER cons1)");
        }
        try (var ps = con.prepareStatement("UPSERT INTO tab_test1(a,b) VALUES(?,?)")) {
            for (int i = 1; i < 101; ++i) {
                ps.setInt(1, i);
                ps.setString(2, "value-" + Integer.toString(i + 100500, 35));
                ps.addBatch();
            }
            ps.executeBatch();
        }
        con.setAutoCommit(false);
    }

    private static void cleanup(Connection con) {
        try {
            try (var ps = con.prepareStatement(
                    "SELECT a, b FROM tab_test1 ORDER BY a")) {
                try (var rs = ps.executeQuery()) {
                    LOG.info("Table data on exit:");
                    while (rs.next()) {
                        LOG.info("{} -> {}", rs.getInt(1), rs.getString(2));
                    }
                    LOG.info("End table data.");
                }
            }
        } catch (Exception ex) {
        }
        try {
            dropTables(con);
        } catch (Exception ex) {
            LOG.error("Cleanup failed", ex);
        }
    }

    private static void dropTables(Connection con) throws Exception {
        con.setAutoCommit(true);
        try (var stmt = con.createStatement()) {
            stmt.execute("DROP TABLE tab_test1");
            stmt.execute("DROP TOPIC top_test1");
        }
        con.setAutoCommit(false);
    }

    private static Connection getConnection() throws Exception {
        String url = System.getenv("YDB_URL");
        String user = System.getenv("YDB_USER");
        String password = System.getenv("YDB_PASSWORD");
        return DriverManager.getConnection(url, user, password);
    }

    private static TopicClient createTopicClient(Connection con, ExecutorService servicePool) throws Exception {
        return TopicClient.newClient(con.unwrap(GrpcTransport.class))
                .setCompressionExecutor(servicePool)
                .build();
    }

    private static SyncWriter createWriter(TopicClient tc, String topicName) throws Exception {
        String producerId = System.getenv("YDB_PRODUCER");
        if (producerId == null || producerId.length() == 0) {
            producerId = "my-test-producer";
        }
        WriterSettings writerSettings = WriterSettings.newBuilder()
                .setTopicPath(topicName)
                .setProducerId(producerId)
                .build();
        var writer = tc.createSyncWriter(writerSettings);
        writer.init();
        return writer;
    }

    private static void jdbcTest(int recordId, Connection con, ExecutorService servicePool) throws Exception {
        LOG.info("Transaction sample for recordId={}", recordId);
        con.setAutoCommit(false);
        String messageData = "";
        // currently (until YDB 26.2) we need a separate writer per transaction
        SyncWriter writer = null;
        try (var topicClient = createTopicClient(con, servicePool)) {
            writer = createWriter(topicClient, "top_test1");
            // select statement
            try (var ps = con.prepareStatement("SELECT a,b FROM tab_test1 WHERE a=?")) {
                ps.setInt(1, recordId);
                try (var rs = ps.executeQuery()) {
                    while (rs.next()) {
                        messageData = rs.getString(2);
                        LOG.info("output1: {}", messageData);
                    }
                }
            }
            // transaction details
            var trans = con.unwrap(YdbTransaction.class);
            LOG.info("transactionId: {}\tsessionId={}", trans.getId(), trans.getSessionId());
            // write to topic and wait
            writer.send(Message.of(("message " + messageData + "\n").getBytes(StandardCharsets.UTF_8)),
                    SendSettings.newBuilder().setTransaction(trans).build());
            writer.flush();
            LOG.info("Message flushed");
            // update statement
            try (var ps = con.prepareStatement("UPDATE tab_test1 SET b='Operation 'u || b WHERE a=?")) {
                ps.setInt(1, recordId);
                ps.executeUpdate();
            }
            LOG.info("Update performed");
            // commit or rollback
            if (recordId % 2 == 1) {
                con.commit();
                LOG.info("Transaction committed");
            } else {
                con.rollback();
                LOG.info("Transaction rolled back");
            }
        } finally {
            if (writer != null) {
                writer.shutdown(30L, TimeUnit.SECONDS);
            }
        }
    }

    private static void dumpThreads() {
        LOG.info("Performing pre-closure thread dump.");
        var threadMXBean = ManagementFactory.getThreadMXBean();
        var tis = threadMXBean.getThreadInfo(threadMXBean.getAllThreadIds(), 100);
        for (var ti : tis) {
            LOG.info("#{} {} -> {}", ti.getThreadId(), ti.getThreadName(), ti.getThreadState());
            int counter = 0;
            for (var ste : ti.getStackTrace()) {
                LOG.info("\t {}", ste);
                if (++counter > 10) {
                    break;
                }
            }
            LOG.info("***");
        }
    }

}
