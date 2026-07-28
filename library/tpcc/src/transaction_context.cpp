#include <tpcc/transaction_context.h>

namespace NTPCC {

std::atomic<size_t> TransactionsInflight{0};

} // namespace NTPCC
