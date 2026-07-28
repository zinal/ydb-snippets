#pragma once

#include <tpcc/postgres/pg_connection_pool.h>
#include <tpcc/postgres/transactions.h>
#include <tpcc/terminal_stats.h>
#include <tpcc/transaction_context.h>
#include <tpcc/util/future.h>
#include <tpcc/util/task_queue.h>

#include <atomic>
#include <memory>
#include <stop_token>

namespace NTPCC {

class alignas(64) TTerminal {
public:
    TTerminal(
        size_t terminalID,
        size_t warehouseID,
        size_t warehouseCount,
        ITaskQueue& taskQueue,
        PgConnectionPool* connectionPool,
        bool noDelays,
        std::stop_token stopToken,
        std::atomic<bool>& stopWarmup,
        std::shared_ptr<TTerminalStats>& stats,
        int simulateTransactionMs = 0,
        int simulateTransactionSelect1 = 0);

    TTerminal(const TTerminal&) = delete;
    TTerminal& operator=(TTerminal&) = delete;
    TTerminal(TTerminal&&) = delete;
    TTerminal& operator=(TTerminal&&) = delete;

    size_t GetID() const { return Context.TerminalID; }

    void Start();
    bool IsDone() const { return Done.load(std::memory_order_relaxed); }

private:
    TFuture<void> Run();

    ITaskQueue& TaskQueue;
    PgConnectionPool* ConnectionPool;
    TTransactionContext Context;
    bool NoDelays;
    std::stop_token StopToken;
    std::atomic<bool>& StopWarmup;
    std::shared_ptr<TTerminalStats> Stats;

    std::atomic<bool> Done{false};
    bool Started = false;
    bool WarmupWasStopped = false;
};

} // namespace NTPCC
