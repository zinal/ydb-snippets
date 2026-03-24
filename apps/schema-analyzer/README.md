# YDB Schema Analyzer

Python CLI application that:

1. Connects to YDB with selectable authentication mode and optional custom CA certificate.
2. Lists tables recursively under a given path.
3. Reads each table schema.
4. Compares schemas and groups tables with the same structure.

Comparison rules:

- Takes into account:
  - Number of columns
  - Column data types
  - Primary key structure
  - Secondary indexes over columns (including index type and covered columns)
- Ignores:
  - Actual column names
  - Index names
  - Partitioning settings

Only groups with at least two tables are printed.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python schema_analyzer.py \
  --endpoint "grpcs://ydb.serverless.yandexcloud.net:2135" \
  --database "/ru-central1/b1.../etn..." \
  --auth-mode env
```

### Arguments

- `--endpoint` (required): YDB endpoint.
- `--database` (required): YDB database path.
- `--start-path`: path in database to scan recursively, default `.`.
- `--auth-mode`: one of:
  - `none` - anonymous auth
  - `env` - auth from environment variables
  - `static` - username/password
  - `metadata` - VM metadata credentials
  - `sakey` - service account key file
  - `token` - access token
- `--ca-file`: optional CA certificate file in PEM format.
- `--wait-timeout`: driver wait timeout in seconds (default: `10`).
- `--skip-describe-errors`: skip tables that fail describe instead of stopping.
- `--verbose`: verbose logs.

### Auth-specific arguments

- `--auth-mode static`: requires `--static-user` and `--static-password`
- `--auth-mode sakey`: requires `--sa-key-file`
- `--auth-mode token`: requires `--access-token`

## Examples

Anonymous:

```bash
python schema_analyzer.py \
  --endpoint "grpc://localhost:2136" \
  --database "/Root" \
  --auth-mode none
```

Static credentials:

```bash
python schema_analyzer.py \
  --endpoint "grpcs://host:2135" \
  --database "/Root/db1" \
  --auth-mode static \
  --static-user "root" \
  --static-password "secret" \
  --ca-file "./ca.pem"
```

Service account key:

```bash
python schema_analyzer.py \
  --endpoint "grpcs://host:2135" \
  --database "/Root/db1" \
  --auth-mode sakey \
  --sa-key-file "./sa-key.json"
```
