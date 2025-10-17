package ydb.tech.samples.jdbc.concurrent;

import java.sql.Connection;
import java.sql.DriverManager;

/**
 *
 * @author zinal
 */
public class JdbcConcurrent {

    public static void main(String[] args) {
        long tvStart = System.currentTimeMillis();
        try {
            prepareTables();
            System.out.println("Tables created!");
            try {
                tliDemo();
                System.out.println("Strange - expected TLI error, but none happened.");
            } catch (Exception ex) {
                System.out.println("Error: " + ex.toString());
            }
            dropTables();
            System.out.println("Tables dropped!");
        } catch (Exception ex) {
            ex.printStackTrace(System.out);
        }
        long tvFinish = System.currentTimeMillis();
        System.out.println("Execution millis: " + (tvFinish - tvStart));
    }

    private static Connection getConnection() throws Exception {
        String url = System.getenv("YDB_URL");
        if (url == null || url.length() == 0) {
            throw new Exception("Missing JDBC URL, has to be specified in YDB_URL env");
        }
        String user = System.getenv("YDB_USER");
        if (user == null) {
            return DriverManager.getConnection(url);
        }
        String password = System.getenv("YDB_PASSWORD");
        return DriverManager.getConnection(url, user, password);
    }

    private static void prepareTables() throws Exception {
        try (var con = getConnection(); var stmt = con.createStatement()) {
            con.setAutoCommit(true);
            stmt.execute("CREATE TABLE test1(id Text NOT NULL, file_name Text, PRIMARY KEY(id))");
            stmt.execute("CREATE TABLE test2(id Text NOT NULL, message_id Text, PRIMARY KEY(id))");
            stmt.execute("UPSERT INTO test1(id, file_name) VALUES"
                    + "('test1-1', 'file1.txt'), ('test1-2', 'file2.txt')");
            stmt.execute("UPSERT INTO test2(id, message_id) VALUES"
                    + "('test2-1', 'message1'), ('test2-2', 'message2')");
        }
    }

    private static void dropTables() throws Exception {
        try (var con = getConnection(); var stmt = con.createStatement()) {
            con.setAutoCommit(true);
            stmt.execute("DROP TABLE test1;");
            stmt.execute("DROP TABLE test2;");
        }
    }

    private static void tliDemo() throws Exception {
        try (var con1 = getConnection(); var con2 = getConnection()) {
            con1.setAutoCommit(false);
            con2.setAutoCommit(false);
            try (var ps = con1.prepareStatement("SELECT file_name, id FROM test1 WHERE id=?")) {
                ps.setString(1, "test1-1");
                try (var rs = ps.executeQuery()) {
                    if (rs.next()) {
                        System.out.println("(main) file_name = " + rs.getString(1) + ", id = " + rs.getString(2));
                    }
                }
            }
            try (var ps = con1.prepareStatement("UPDATE test1 SET file_name=? WHERE id=? RETURNING file_name, id")) {
                ps.setString(1, "file1-up.txt");
                ps.setString(2, "test1-1");
                try (var rs = ps.executeQuery()) {
                    if (rs.next()) {
                        System.out.println("(sub) file_name = " + rs.getString(1) + ", id = " + rs.getString(2));
                    }
                }
            }
            con2.commit();
            try (var ps = con1.prepareStatement("UPDATE test2 SET message_id=? WHERE id=? RETURNING message_id, id")) {
                ps.setString(1, "message1-up");
                ps.setString(2, "test2-1");
                try (var rs = ps.executeQuery()) {
                    if (rs.next()) {
                        System.out.println("(main) message_id = " + rs.getString(1) + ", id = " + rs.getString(2));
                    }
                }
            }
            con1.commit();
        }
    }
}
