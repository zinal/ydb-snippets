package ydb.tech.samples.jdbc.basic;

import java.sql.DriverManager;

/**
 *
 * @author zinal
 */
public class JdbcBasic {

    public static void main(String[] args) {
        long tvStart = System.currentTimeMillis();
        try {
            jdbcTest();
            System.out.println("SUCCESS! ");
        } catch(Exception ex) {
            System.out.println("FAILED! " + ex.toString());
        }
        long tvFinish = System.currentTimeMillis();
        System.out.println("Execution millis: " + (tvFinish - tvStart));
    }

    private static void jdbcTest() throws Exception {
        String url = System.getenv("YDB_URL");
        String user = System.getenv("YDB_USER");
        String password = System.getenv("YDB_PASSWORD");
        try (var con = DriverManager.getConnection(url, user, password)) {
            var ps = con.prepareStatement("SELECT 123 AS aaa");
            var rs = ps.executeQuery();
            while (rs.next()) {
                System.out.println("\toutput: " + rs.getString(1));
            }
        }
    }
}
