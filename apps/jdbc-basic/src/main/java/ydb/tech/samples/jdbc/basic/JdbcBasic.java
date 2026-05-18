package ydb.tech.samples.jdbc.basic;

import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.DriverManager;
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

    public static void main(String[] args) {
        long tvStart = System.currentTimeMillis();
        boolean tablesCreated = false;
        try (var con = getConnection()) {
            createTables(con);
            tablesCreated = true;
            try (var writer = createWriter(con, "top_test1")) {
                jdbcTest(con, writer);
            }
            System.out.println("SUCCESS! ");
        } catch (Exception ex) {
            System.out.println("FAILED! " + ex.toString());
        } finally {
            if (tablesCreated) {
                try {
                    dropTables(getConnection());
                } catch (Exception ex) {
                }
            }
        }
        long tvFinish = System.currentTimeMillis();
        System.out.println("Execution millis: " + (tvFinish - tvStart));
    }

    private static void createTables(Connection con) throws Exception {
        con.setAutoCommit(true);
        try (var stmt = con.createStatement()) {
            stmt.execute("CREATE TABLE tab_test1(a Int32, b Text, PRIMARY KEY(a))");
            stmt.execute("CREATE TOPIC top_test1(CONSUMER cons1)");
            stmt.execute("UPSERT INTO tab_test1(a,b) VALUES(1, 'One'u), (2, 'Two'u)");
        }
        con.setAutoCommit(false);
    }

    private static void dropTables(Connection con) throws Exception {
        /*
        con.setAutoCommit(true);
        try (var stmt = con.createStatement()) {
            stmt.execute("DROP TABLE tab_test1");
            stmt.execute("DROP TOPUC top_test1");
        }
        con.setAutoCommit(false);
         */
    }

    private static Connection getConnection() throws Exception {
        String url = System.getenv("YDB_URL");
        String user = System.getenv("YDB_USER");
        String password = System.getenv("YDB_PASSWORD");
        return DriverManager.getConnection(url, user, password);
    }

    private static WriteContext createWriter(Connection con, String topicName) throws Exception {
        WriterSettings writerSettings = WriterSettings.newBuilder()
                .setTopicPath(topicName)
                .build();
        var transport = con.unwrap(GrpcTransport.class);
        var client = TopicClient.newClient(transport).build();
        try {
            var writer = client.createSyncWriter(writerSettings);
            writer.initAndWait();
            return new WriteContext(client, topicName, writer);
        } catch (Exception ex) {
            try {
                client.close();
            } catch (Exception ex2) {
            }
            throw ex;
        }
    }

    private static void jdbcTest(Connection con, WriteContext writeContext) throws Exception {
        con.setAutoCommit(false);
        var writer = writeContext.getWriter();
        String messageData = "";
        try (var ps = con.prepareStatement("SELECT a,b FROM tab_test1 WHERE a=1")) {
            try (var rs = ps.executeQuery()) {
                while (rs.next()) {
                    messageData = rs.getString(2);
                    System.out.println("\toutput1: " + messageData);
                }
            }
        }
        var trans = con.unwrap(YdbTransaction.class);
        System.out.println("\ttransactionId: " + trans.getId() + "\tsessionId=" + trans.getSessionId());
        writer.send(Message.of(messageData.getBytes(StandardCharsets.UTF_8)),
                SendSettings.newBuilder().setTransaction(trans).build());
        writer.flush();
        con.commit();
    }

    static class WriteContext implements AutoCloseable {

        final TopicClient client;
        final String topicName;
        final SyncWriter writer;

        public WriteContext(TopicClient client, String topicName, SyncWriter writer) {
            this.client = client;
            this.topicName = topicName;
            this.writer = writer;
        }

        public TopicClient getClient() {
            return client;
        }

        public String getTopicName() {
            return topicName;
        }

        public SyncWriter getWriter() {
            return writer;
        }

        @Override
        public void close() {
            try {
                writer.shutdown(30L, TimeUnit.SECONDS);
            } catch (Exception ex) {
                LOG.error("SyncWriter shutdown has not completed", ex);
            }
            try {
                client.close();
            } catch (Exception ex) {
                LOG.error("TopicClient closure failed", ex);
            }
        }
    }
}
