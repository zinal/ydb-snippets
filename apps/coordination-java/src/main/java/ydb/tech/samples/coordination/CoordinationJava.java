package ydb.tech.samples.coordination;

import java.io.Console;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import tech.ydb.coordination.CoordinationSession;
import tech.ydb.coordination.SemaphoreLease;

/**
 *
 * @author mzinal
 */
public class CoordinationJava {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(CoordinationJava.class);

    public static void main(String[] args) {
        String fname = "connection.xml";
        if (args.length > 0) {
            fname = args[0];
        }
        LOG.info("Initializing...");
        try (YdbConnector yc = new YdbConnector(fname)) {
            String coordPath = yc.getDatabase() + "/coordination";
            var descResult = yc.getSchemeClient().describePath(coordPath).join();
            if (!descResult.isSuccess()) {
                LOG.info("Creating coordination node {}...", coordPath);
                yc.getCoordinationClient().createNode(coordPath).join().expectSuccess();
            }
            LOG.info("Opening session...");
            CoordinationSession session = yc.newCoordinationSession(coordPath);
            LOG.info("Connecting session...");
            session.connect().join().expectSuccess();
            ArrayList<SemaphoreLease> leases = new ArrayList<>();
            for (int i=0; i<3; ++i) {
                String semaName = "sema-" + String.valueOf(i);
                LOG.info("Acquiring semaphore {}...", semaName);
                var result = session
                        .acquireEphemeralSemaphore(semaName, true, Duration.ofHours(1L))
                        .join();
                result.getStatus().expectSuccess();
                leases.add(result.getValue());
            }
            
            waitEnter();
            
            Collections.reverse(leases);
            for (SemaphoreLease sl : leases) {
                LOG.info("Releasing semaphore {}", sl.getSemaphoreName());
                sl.release().join();
                waitEnter();
            }

            LOG.info("All done!");
        } catch(Exception ex) {
            LOG.error("Failed", ex);
            System.exit(1);
        }
    }
    
    private static void waitEnter() {
        Console c = System.console();
        if (c != null) {
            c.format("\nPress ENTER to proceed.\n");
            c.readLine();
        }
    }
}
