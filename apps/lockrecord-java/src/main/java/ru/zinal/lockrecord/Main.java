package ru.zinal.lockrecord;

import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 *
 * @author zinal
 */
public class Main {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(Main.class);

    final YdbConnector yc;
    final YdbLockRecord locker;
    final AtomicInteger owner = new AtomicInteger(-1);
    final AtomicLong execCount = new AtomicLong(0);

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

        LOG.info("Total workload executions within the lock: {}", execCount.get());
    }

    void startExecutors() {
        LOG.info("Starting executors...");
        for (int i=0; i<50; ++i) {
            var t = new Thread(new Executor(i));
            t.setDaemon(true);
            t.start();
        }
        LOG.info("All executors are running!");
    }

    void work(int i) {
        pause();
        locker.lock();
        owner.set(i);
        try {
            realWork(i);
        } finally {
            owner.set(-1);
            locker.unlock();
        }
    }

    void realWork(int i) {
        LOG.debug("Work started: " + i);
        validate(i);
        pause();
        validate(i);
        pause();
        validate(i);
        LOG.debug("Work completed: " + i);
        execCount.addAndGet(1L);
    }

    void pause() {
        try {
            Thread.sleep(ThreadLocalRandom.current().nextLong(10L, 50L));
        } catch(InterruptedException ix) {}
    }

    void validate(int i) {
        int cur = owner.get();
        if (i!=cur) {
            LOG.warn("Expected owner {}, actual owner {}", i, cur);
        }
    }

    void waitTime() {
        LOG.info("Running for 5 minutes...");
        final long tvFinish = System.currentTimeMillis() + (5L*60L*1000L);
        do {
            try { Thread.sleep(500L); } catch(InterruptedException ix) {}
        } while (tvFinish > System.currentTimeMillis());
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
