package main

import (
	"context"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/client"
	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/find"
	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/repair"
)

func main() {
	log.SetFlags(0)
	if len(os.Args) < 2 {
		usage(os.Stderr)
		os.Exit(2)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var err error
	switch os.Args[1] {
	case "find":
		err = runFind(ctx, os.Args[2:])
	case "repair":
		err = runRepair(ctx, os.Args[2:])
	case "-h", "--help", "help":
		usage(os.Stdout)
		return
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n\n", os.Args[1])
		usage(os.Stderr)
		os.Exit(2)
	}
	if err != nil {
		log.Printf("ERROR: %v", err)
		os.Exit(1)
	}
}

func usage(w io.Writer) {
	fmt.Fprintf(w, `repair-legacy-tables — find and repair YDB tables created in legacy mode

Uses legacy private gRPC (TGRpcServer.SchemeDescribe / SchemeOperation).

Commands:
  find     Walk scheme tree and list tables that need repair
  repair   Repair tables listed in a file (from find --output)

Auth: anonymous by default; set YDB_TOKEN or pass --token-file.

Examples:
  repair-legacy-tables find --endpoint grpc://host:2135 \
      --database /Root/db --output legacy_tables.txt

  repair-legacy-tables repair --endpoint grpc://host:2135 \
      --pool-kind ssd --tables-file legacy_tables.txt

  # Drop each <table>_bak right after that table is repaired
  repair-legacy-tables repair --endpoint grpc://host:2135 \
      --pool-kind ssd --tables-file legacy_tables.txt --drop-backup
`)
}

func commonFlags(fs *flag.FlagSet) (endpoint, tokenFile, caFile *string, insecure *bool, timeout *time.Duration) {
	endpoint = fs.String("endpoint", "", "gRPC endpoint (grpc://host:2135 or grpcs://host:2135)")
	tokenFile = fs.String("token-file", "", "Token file (overrides YDB_TOKEN); anonymous if unset")
	caFile = fs.String("ca-file", "", "CA certificate for grpcs://")
	insecure = fs.Bool("insecure", false, "Skip TLS certificate verification (grpcs, lab/dev only)")
	timeout = fs.Duration("timeout", 2*time.Minute, "Per-RPC / poll timeout")
	return
}

func dialFromFlags(ctx context.Context, endpoint, tokenFile, caFile string, insecure bool, timeout time.Duration) (*client.Client, error) {
	if endpoint == "" {
		return nil, fmt.Errorf("--endpoint is required")
	}
	token, err := client.ResolveToken(tokenFile)
	if err != nil {
		return nil, err
	}
	return client.Dial(ctx, client.Options{
		Endpoint: endpoint,
		Token:    token,
		CAFile:   caFile,
		Insecure: insecure,
		Timeout:  timeout,
	})
}

func runFind(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("find", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	endpoint, tokenFile, caFile, insecure, timeout := commonFlags(fs)
	database := fs.String("database", "", "Database path (e.g. /Root/database)")
	path := fs.String("path", "", "Start directory (default: same as --database)")
	output := fs.String("output", "", "Also write results to this file (path\\treason)")
	includeSys := fs.Bool("include-sys", false, "Also walk directories whose names start with '.'")
	if err := parseFlags(fs, args); err != nil {
		return err
	}
	if *database == "" {
		return fmt.Errorf("--database is required")
	}
	start := *path
	if start == "" {
		start = *database
	}

	c, err := dialFromFlags(ctx, *endpoint, *tokenFile, *caFile, *insecure, *timeout)
	if err != nil {
		return err
	}
	defer c.Close()

	auth := "anonymous"
	if tok, _ := client.ResolveToken(*tokenFile); tok != "" {
		auth = "token"
	}
	logger := log.New(os.Stderr, "", log.LstdFlags)
	logger.Printf("Scanning path=%s auth=%s", start, auth)

	var out io.Writer = os.Stdout
	var outFile *os.File
	if *output != "" {
		outFile, err = os.Create(*output)
		if err != nil {
			return fmt.Errorf("create output file: %w", err)
		}
		defer outFile.Close()
		out = io.MultiWriter(os.Stdout, outFile)
	}

	res, err := find.Run(ctx, c, find.Options{
		StartPath:  start,
		IncludeSys: *includeSys,
		Out:        out,
		Log:        logger,
	})
	if err != nil {
		return err
	}
	logger.Printf("Done: tables=%d, legacy=%d, errors=%d", res.TablesChecked, res.Legacy, res.Errors)
	if res.Errors > 0 {
		return fmt.Errorf("completed with %d describe error(s)", res.Errors)
	}
	return nil
}

func runRepair(ctx context.Context, args []string) error {
	fs := flag.NewFlagSet("repair", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	endpoint, tokenFile, caFile, insecure, timeout := commonFlags(fs)
	tablesFile := fs.String("tables-file", "", "File with table paths (from find --output)")
	poolKind := fs.String("pool-kind", "", "PreferredPoolKind for default family (e.g. ssd)")
	tempPrefix := fs.String("temp-prefix", "temp_", "Prefix for temporary copy name")
	backupSuffix := fs.String("backup-suffix", "_bak", "Suffix for renamed original table")
	dropBackup := fs.Bool("drop-backup", false, "Drop <table>_bak immediately after each successful rename")
	dryRun := fs.Bool("dry-run", false, "Check and print plan without modifying scheme")
	if err := parseFlags(fs, args); err != nil {
		return err
	}
	if *tablesFile == "" {
		return fmt.Errorf("--tables-file is required")
	}
	if *poolKind == "" {
		return fmt.Errorf("--pool-kind is required")
	}

	c, err := dialFromFlags(ctx, *endpoint, *tokenFile, *caFile, *insecure, *timeout)
	if err != nil {
		return err
	}
	defer c.Close()

	auth := "anonymous"
	if tok, _ := client.ResolveToken(*tokenFile); tok != "" {
		auth = "token"
	}
	logger := log.New(os.Stderr, "", log.LstdFlags)
	logger.Printf("Starting repair: endpoint=%s tables-file=%s pool_kind=%q auth=%s dry_run=%v drop_backup=%v",
		*endpoint, *tablesFile, *poolKind, auth, *dryRun, *dropBackup)

	res, err := repair.Run(ctx, c, repair.Options{
		TablesFile:   *tablesFile,
		PoolKind:     *poolKind,
		TempPrefix:   *tempPrefix,
		BackupSuffix: *backupSuffix,
		DropBackup:   *dropBackup,
		DryRun:       *dryRun,
		Log:          logger,
		Out:          os.Stdout,
	})
	if err != nil {
		if res != nil {
			logger.Printf("Stopped: total=%d, repaired=%d, skipped=%d", res.Total, res.Repaired, res.Skipped)
		}
		return err
	}
	logger.Printf("Done: total=%d, repaired=%d, skipped_already_ok=%d, backups_dropped=%d",
		res.Total, res.Repaired, res.Skipped, res.BackupsDropped)
	return nil
}
