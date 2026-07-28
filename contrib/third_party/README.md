# Third-party dependencies for TPC-C

Vendored libraries used by `contrib/tpcc-postgres`. Initialize with:

```bash
git submodule update --init --recursive contrib/third_party/fmt \
  contrib/third_party/spdlog contrib/third_party/gflags \
  contrib/third_party/libpqxx contrib/third_party/ftxui \
  contrib/third_party/googletest
```

| Package | Purpose |
|---------|---------|
| fmt | String formatting |
| spdlog | Logging |
| gflags | CLI flags |
| libpqxx | PostgreSQL C++ client (also requires system `libpq-dev`) |
| ftxui | Terminal UI (optional at runtime) |
| googletest | Unit tests |

System dependency not vendored here: **libpq-dev** (PostgreSQL client headers).

Optional: **libgoogle-perftools-dev** for tcmalloc.
