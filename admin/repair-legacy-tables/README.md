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
4. With `--drop-backup`: after **all** tables in the batch succeed, drop every
   `<name>_bak` created in this run (on mid-batch error backups are kept)

```bash
export YDB_TOKEN="$(cat ydb-token)"

./bin/repair-legacy-tables repair \
  --endpoint grpcs://ydb-host:2135 --ca-file ca.crt \
  --pool-kind ssd \
  --tables-file legacy_tables.txt

# same, then remove backups at the end
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
is kept as `<name>_bak`; pass `--drop-backup` to remove those backups at the end
of a fully successful run.

## Regenerate protos

```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
make generate
```
