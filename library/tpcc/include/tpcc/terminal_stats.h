#pragma once

#include <tpcc/constants.h>
#include <tpcc/util/histogram.h>
#include <tpcc/util/spinlock.h>

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>

namespace NTPCC {

class TTerminalStats {
    static constexpr uint64_t DefaultResolution = 4096;
    static constexpr uint64_t HighResolution = 16384;
    static constexpr uint64_t MaxResolution = 32768;

public:
    struct TTransactionStats {
        explicit TTransactionStats(uint64_t histogramResolution = DefaultResolution)
            : LatencyHistogramMs(histogramResolution, MaxResolution)
            , LatencyHistogramFullMs(histogramResolution, MaxResolution)
            , LatencyHistogramPure(histogramResolution, MaxResolution)
        {}

        void Collect(TTransactionStats& dst) const {
            dst.OK.fetch_add(OK.load(std::memory_order_relaxed), std::memory_order_relaxed);
            dst.Failed.fetch_add(Failed.load(std::memory_order_relaxed), std::memory_order_relaxed);
            dst.UserAborted.fetch_add(UserAborted.load(std::memory_order_relaxed), std::memory_order_relaxed);

            std::lock_guard guard(HistLock);
            dst.LatencyHistogramMs.Add(LatencyHistogramMs);
            dst.LatencyHistogramFullMs.Add(LatencyHistogramFullMs);
            dst.LatencyHistogramPure.Add(LatencyHistogramPure);
        }

        void Clear() {
            OK.store(0, std::memory_order_relaxed);
            Failed.store(0, std::memory_order_relaxed);
            UserAborted.store(0, std::memory_order_relaxed);

            std::lock_guard guard(HistLock);
            LatencyHistogramMs.Reset();
            LatencyHistogramFullMs.Reset();
            LatencyHistogramPure.Reset();
        }

        std::atomic<size_t> OK = 0;
        std::atomic<size_t> Failed = 0;
        std::atomic<size_t> UserAborted = 0;

        mutable TSpinLock HistLock;
        THistogram LatencyHistogramMs;
        THistogram LatencyHistogramFullMs;
        THistogram LatencyHistogramPure;
    };

public:
    TTerminalStats(bool highResHistogram = false) {
        if (highResHistogram) {
            uint64_t histogramResolution = HighResolution;
            for (auto& stats : PerTransactionTypeStats) {
                stats.LatencyHistogramMs = THistogram(histogramResolution, MaxResolution);
                stats.LatencyHistogramFullMs = THistogram(histogramResolution, MaxResolution);
                stats.LatencyHistogramPure = THistogram(histogramResolution, MaxResolution);
            }
        }
    }

    const TTransactionStats& GetStats(ETransactionType type) const {
        return PerTransactionTypeStats[static_cast<size_t>(type)];
    }

    void AddOK(
        ETransactionType type,
        std::chrono::milliseconds latency,
        std::chrono::milliseconds latencyFull,
        std::chrono::microseconds latencyPure)
    {
        auto& stats = PerTransactionTypeStats[static_cast<size_t>(type)];
        stats.OK.fetch_add(1, std::memory_order_relaxed);
        auto latencyPureMs = std::chrono::duration_cast<std::chrono::milliseconds>(latencyPure).count();
        {
            std::lock_guard guard(stats.HistLock);
            stats.LatencyHistogramMs.RecordValue(latency.count());
            stats.LatencyHistogramFullMs.RecordValue(latencyFull.count());
            stats.LatencyHistogramPure.RecordValue(latencyPureMs);
        }
    }

    void IncFailed(ETransactionType type) {
        PerTransactionTypeStats[static_cast<size_t>(type)].Failed.fetch_add(1, std::memory_order_relaxed);
    }

    void IncUserAborted(ETransactionType type) {
        PerTransactionTypeStats[static_cast<size_t>(type)].UserAborted.fetch_add(1, std::memory_order_relaxed);
    }

    void Collect(TTerminalStats& dst) const {
        for (size_t i = 0; i < PerTransactionTypeStats.size(); ++i) {
            PerTransactionTypeStats[i].Collect(dst.PerTransactionTypeStats[i]);
        }
    }

    void Clear() {
        for (auto& stats: PerTransactionTypeStats) {
            stats.Clear();
        }
    }

    void ClearOnce() {
        bool expected = false;
        if (WasCleared.compare_exchange_strong(expected, true, std::memory_order_relaxed)) {
            Clear();
        }
    }

private:
    std::array<TTransactionStats, TRANSACTION_TYPE_COUNT> PerTransactionTypeStats;
    std::atomic<bool> WasCleared{false};
};

} // namespace NTPCC
