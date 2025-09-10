package ydb.tech.samples.kilobyter;

import java.time.Instant;
import tech.ydb.table.query.Params;
import tech.ydb.table.values.PrimitiveValue;

/**
 *
 * @author mzinal
 */
public class YdbKilobyter {
    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(YdbKilobyter.class);

    public static void main(String[] args) {
        String configFile = "connect.xml";
        if (args.length > 0) {
            configFile = args[0];
        }
        try (YdbConnector conn = new YdbConnector(configFile)) {
            LOG.info("Starting...");
            run(conn);
            LOG.info("Completed!");
        } catch(Exception ex) {
            LOG.error("FATAL", ex);
            System.exit(1);
        }
    }

    private static void run(YdbConnector conn) {
        String kilo = makeKilo();
        var start = Instant.now();
        var end = start.plusSeconds(10);
        var step = start;
        int count = 0;
        while (step.compareTo(end) < 0) {
            sendReceive(conn, kilo);
            ++count;
            step = Instant.now();
        }
        long duration = end.toEpochMilli() - start.toEpochMilli();
        double rate = (duration > 0L) ? ((double) count) * 1000.0 / ((double)duration) : 0.0;
        LOG.info("Rate is {}", String.format("%.2f", rate));
    }

    private static String makeKilo() {
        final StringBuilder sb = new StringBuilder();
        for (int i=0; i<1024; ++i) {
            sb.append('a');
        }
        return sb.toString();
    }

    private static void sendReceive(YdbConnector conn, String kilo) {
        Params params = Params.of("$p1", PrimitiveValue.newText(kilo));
        var rs = conn.sqlReadWrite("DECLARE $p1 AS Text; SELECT $p1;", params).getResultSet(0);
        if (! rs.next()) {
            throw new IllegalStateException("Strange 1");
        }
        String ret = rs.getColumn(0).getText();
        if (! kilo.equals(ret)) {
            throw new IllegalStateException("Strange 2");
        }
        if (kilo == ret) {
            throw new IllegalStateException("Strange 3");
        }
    }
}
