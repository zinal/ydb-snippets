#pragma once

#include <tpcc/postgres/pg_session.h>
#include <tpcc/transaction_context.h>
#include <tpcc/util/future.h>

namespace NTPCC {

TFuture<bool> GetNewOrderTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

TFuture<bool> GetDeliveryTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

TFuture<bool> GetOrderStatusTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

TFuture<bool> GetPaymentTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

TFuture<bool> GetStockLevelTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

TFuture<bool> GetSimulationTask(
    TTransactionContext& context,
    std::chrono::microseconds& latency,
    PgSession& session);

} // namespace NTPCC
