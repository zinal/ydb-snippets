# repair-legacy-tables

Go utility to **find** and **repair** YDB row-tables created in legacy mode
(missing `PartitionConfig.ColumnFamilies[Id=0].StorageConfig`), so that
`ALTER TABLE … ADD FAMILY` works.

Uses the legacy private gRPC API (`TGRpcServer.SchemeDescribe` /
`SchemeOperation` / `SchemeOperationStatus`) — the same path as
`ydbd db schema execute` and `ydbd db schema describe`.

Minimal proto stubs live under `protos/` and are generated into `pkg/kikimr/`.

## Build

```bash
cd admin/repair-legacy-tables
go mod tidy
make build
# binary: bin/repair-legacy-tables
```

`make build` sets `CGO_ENABLED=0` so the binary is statically linked and does
**not** depend on the host GLIBC version (avoids errors like
`version GLIBC_2.34 not found` when copying the binary to older Linux hosts).

If you call `go build` directly, pass the same flag:

```bash
CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' \
  -o bin/repair-legacy-tables ./cmd/repair-legacy-tables
```

```bash
# verify: should print "statically linked" / "not a dynamic executable"
file bin/repair-legacy-tables
ldd bin/repair-legacy-tables || true
```

Requirements: Go 1.22+, `protoc` + `protoc-gen-go` + `protoc-gen-go-grpc` only if you regenerate stubs (`make generate`).

## Auth

- **Anonymous** by default
- Token from `YDB_TOKEN` or `--token-file` (sent as `SecurityToken`)

## Find legacy tables

Walks the scheme tree with `SchemeDescribe` (children + partition config).

A table is listed when there is no family with `Id: 0`, or family 0 has no
usable `StorageConfig` (same idea as `admin/viewer/find_legacy_tables.py`).
Tables that already have family-0 `StorageConfig` are skipped. Tables with
`ChannelProfileId` set are treated as unsafe and are not listed for repair.

```bash
./bin/repair-legacy-tables find \
  --endpoint grpc://ydb-host:2135 \
  --database /Root/database \
  --output legacy_tables.txt

# subtree only
./bin/repair-legacy-tables find \
  --endpoint grpcs://ydb-host:2135 --ca-file ca.crt \
  --database /Root/database --path /Root/database/schema1 \
  --output legacy_tables.txt
```

Stdout / `--output`: `path<TAB>reason` (one legacy table per line). Progress on stderr.

## Repair from a list

Reads paths from a file produced by `find` (first column; `#` comments and blank lines ignored).

For each table:

1. Re-check via `SchemeDescribe` that repair is still needed  
   - already repaired → skip and continue  
   - unsafe / other error → **stop**
2. `CreateTable` + `CopyFromTable` with default family `StorageConfig` (`PreferredPoolKind`)
3. Move original → `<name>_bak`, temp copy → original
4. With `--drop-backup`: drop `<name>_bak` immediately after that table’s rename
   and post-check succeed

```bash
export YDB_TOKEN="$(cat ydb-token)"

./bin/repair-legacy-tables repair \
  --endpoint grpcs://ydb-host:2135 --ca-file ca.crt \
  --pool-kind ssd \
  --tables-file legacy_tables.txt

# same, drop each backup right after its table is repaired
./bin/repair-legacy-tables repair \
  --endpoint grpcs://ydb-host:2135 --ca-file ca.crt \
  --pool-kind ssd \
  --tables-file legacy_tables.txt \
  --drop-backup

# plan only
./bin/repair-legacy-tables repair \
  --endpoint grpc://ydb-host:2135 \
  --pool-kind ssd \
  --tables-file legacy_tables.txt \
  --dry-run
```

`--pool-kind` must match the database storage pool kind (often `ssd`).

Successfully repaired paths are printed to stdout. By default the original table
is kept as `<name>_bak`; pass `--drop-backup` to remove that backup right after
the repaired table is renamed into place.

## Regenerate protos

```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
make generate
```
