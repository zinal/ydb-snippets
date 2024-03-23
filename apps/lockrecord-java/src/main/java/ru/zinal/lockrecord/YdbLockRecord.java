package ru.zinal.lockrecord;

import java.net.InetAddress;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ThreadLocalRandom;
import tech.ydb.core.Status;
import tech.ydb.core.StatusCode;
import tech.ydb.table.Session;
import tech.ydb.table.SessionRetryContext;
import tech.ydb.table.query.Params;
import tech.ydb.table.transaction.TxControl;
import tech.ydb.table.values.PrimitiveValue;

/**
 * Пример реализации распределенной блокировки через запись в таблице.
 * @author zinal
 */
public class YdbLockRecord {

    private final int lockId;
    private final SessionRetryContext ctx;

    public YdbLockRecord(YdbConnector yc, int lockId) {
        this.lockId = lockId;
        this.ctx = yc.getRetryCtx();
    }

    /**
     * Гарантировать существование необходимых объектов в БД
     */
    public void init() {
        ctx.supplyStatus(session -> session.executeSchemeQuery("CREATE TABLE `sys$lock1`("
                + "id Int32 NOT NULL, locked Bool, owner Utf8, "
                + "PRIMARY KEY(id))")).join().expectSuccess();
    }

    /**
     * Захватить блокировку
     */
    public void lock() {
        while (true) {
            Status status = ctx.supplyStatus(session -> lock(session)).join();
            if (status.isSuccess()) {
                break;
            }
            try {
                Thread.sleep(ThreadLocalRandom.current().nextLong(100L, 500L));
            } catch(InterruptedException ix) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private CompletableFuture<Status> lock(Session session) {
        var result = session.executeDataQuery("DECLARE $id AS Int32; "
                + "SELECT locked FROM `sys$lock1` WHERE id=$id;",
                TxControl.serializableRw().setCommitTx(false),
                Params.of("$id", PrimitiveValue.newInt32(lockId))).join();
        result.getStatus().expectSuccess();
        var data = result.getValue().getResultSet(0);
        final boolean locked;
        if (data.next()) {
            locked = data.getColumn(0).getBool();
        } else {
            locked = false;
        }
        if (locked) {
            return CompletableFuture.completedFuture(Status.of(StatusCode.ALREADY_EXISTS));
        }
        return session.executeDataQuery("DECLARE $id AS Int32; "
                + "DECLARE $owner AS Utf8; "
                + "UPSERT INTO `sys$lock1`(id, locked, owner) VALUES($id, true, $owner);",
                TxControl.id(result.getValue().getTxId()).setCommitTx(true),
                 Params.of("$id", PrimitiveValue.newInt32(lockId),
                         "$owner", PrimitiveValue.newText(getSystemInfo()))).thenApply(v -> v.getStatus());
    }

    private String getSystemInfo() {
        try {
            return InetAddress.getLocalHost().getHostName() + " #" + ProcessHandle.current().pid();
        } catch(Exception ex) {
            throw new RuntimeException(ex);
        }
    }

    /**
     * Освободить блокировку (должна быть предварительно захвачена)
     */
    public void unlock() {
        ctx.supplyStatus(session -> unlock(session)).join().expectSuccess();
    }

    private CompletableFuture<Status> unlock(Session session) {
        return session.executeDataQuery("DECLARE $id AS Int32; "
                + "UPDATE `sys$lock1` SET locked=false, owner=NULL WHERE id=$id",
                TxControl.serializableRw().setCommitTx(true),
                Params.of("$id", PrimitiveValue.newInt32(lockId))).thenApply(v -> v.getStatus());
    }

}
