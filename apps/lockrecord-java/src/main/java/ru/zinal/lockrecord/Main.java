package ru.zinal.lockrecord;

import java.util.concurrent.ThreadLocalRandom;

/**
 *
 * @author zinal
 */
public class Main {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(Main.class);

    final YdbConnector yc;
    final YdbLockRecord locker;

    public static void main(String[] args) {
        try {
            String propFile = "lockrecord.xml";
            if (args.length > 0) {
                propFile = args[0];
            }
            new Main(propFile).run();
        } catch(Exception ex) {
            LOG.error("FATAL: execution failed", ex);
        }
    }

    Main(String propFile) {
        yc = new YdbConnector(YdbConfig.fromFile(propFile));
        locker = new YdbLockRecord(yc, ThreadLocalRandom.current().nextInt(1, 1000));
    }

    void run() {
        startExecutors();
        waitTime();
    }

    void startExecutors() {
        for (int i=0; i<50; ++i) {
            var t = new Thread(new Executor(i));
            t.setDaemon(true);
            t.start();
        }
    }

    void work(int i) {
        locker.lock();
        try {
            realWork(i);
        } finally {
            locker.unlock();
        }
    }

    void realWork(int i) {
        LOG.info("Work started: " + i);
        try {
            Thread.sleep(ThreadLocalRandom.current().nextLong(500L, 2000L));
        } catch(InterruptedException ix) {}
        LOG.info("Work completed: " + i);
    }

    void waitTime() {
        LOG.info("Running for 10 minutes...");
        final long tvFinish = System.currentTimeMillis() + (10L*60L*1000L);
        do {
            try { Thread.sleep(500L); } catch(InterruptedException ix) {}
        } while (tvFinish < System.currentTimeMillis());
        LOG.info("Completed, terminating...");
    }

    class Executor implements Runnable {
        final int i;

        Executor(int i) {
            this.i = i;
        }

        @Override
        public void run() {
            locker.init();
            while (true) {
                work(i);
            }
        }
    }

}
