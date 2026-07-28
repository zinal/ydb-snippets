#pragma once

#include <tpcc/util/task_queue.h>

#include <atomic>
#include <chrono>
#include <stdexcept>

namespace NTPCC {

extern std::atomic<size_t> TransactionsInflight;

struct TTransactionInflightGuard {
    TTransactionInflightGuard() {
        TransactionsInflight.fetch_add(1, std::memory_order_relaxed);
    }

    ~TTransactionInflightGuard() {
        TransactionsInflight.fetch_sub(1, std::memory_order_relaxed);
    }
};

struct TTransactionContext {
    size_t TerminalID;
    size_t WarehouseID;
    size_t WarehouseCount;
    ITaskQueue& TaskQueue;

    int SimulateTransactionMs = 0;
    int SimulateTransactionSelect1 = 0;
};

struct TUserAbortedException : public std::runtime_error {
    TUserAbortedException() : std::runtime_error("User aborted transaction (expected rollback)") {}
};

} // namespace NTPCC
