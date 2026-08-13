package repair

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"strings"

	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/client"
	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/legacy"
)

// ErrAlreadyRepaired means the table does not need repair; continue the batch.
var ErrAlreadyRepaired = errors.New("table already repaired")

// Options for batch repair.
type Options struct {
	TablesFile   string
	PoolKind     string
	TempPrefix   string
	BackupSuffix string
	DropBackup   bool
	DryRun       bool
	Log          *log.Logger
	Out          io.Writer // successfully repaired paths
}

// Result summarizes a repair run.
type Result struct {
	Total          int
	Repaired       int
	Skipped        int
	BackupsDropped int
}

// LoadTablePaths reads absolute paths from a find output file.
// Accepts bare paths or "path\\treason" lines; ignores blanks and # comments.
func LoadTablePaths(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var paths []string
	seen := map[string]struct{}{}
	sc := bufio.NewScanner(f)
	lineno := 0
	for sc.Scan() {
		lineno++
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		p := strings.SplitN(line, "\t", 2)[0]
		p = strings.TrimSpace(p)
		if !strings.HasPrefix(p, "/") {
			return nil, fmt.Errorf("%s:%d: expected absolute table path, got %q", path, lineno, p)
		}
		if _, ok := seen[p]; ok {
			continue
		}
		seen[p] = struct{}{}
		paths = append(paths, p)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return paths, nil
}

// Run repairs tables listed in the tables file. Stops on first non-skip error.
func Run(ctx context.Context, c *client.Client, opt Options) (*Result, error) {
	logger := opt.Log
	if logger == nil {
		logger = log.New(io.Discard, "", 0)
	}
	out := opt.Out
	if out == nil {
		out = io.Discard
	}
	if opt.PoolKind == "" {
		return nil, fmt.Errorf("pool kind is required")
	}
	if opt.TempPrefix == "" {
		opt.TempPrefix = "temp_"
	}
	if opt.BackupSuffix == "" {
		opt.BackupSuffix = "_bak"
	}

	paths, err := LoadTablePaths(opt.TablesFile)
	if err != nil {
		return nil, err
	}
	res := &Result{Total: len(paths)}
	if len(paths) == 0 {
		logger.Printf("No table paths in %s", opt.TablesFile)
		return res, nil
	}

	var backups []string
	for i, path := range paths {
		prefix := fmt.Sprintf("[%d/%d]", i+1, len(paths))
		backupPath, err := repairOne(ctx, c, path, opt, logger)
		if errors.Is(err, ErrAlreadyRepaired) {
			res.Skipped++
			logger.Printf("%s SKIP %v", prefix, err)
			continue
		}
		if err != nil {
			if len(backups) > 0 && opt.DropBackup {
				logger.Printf("Keeping %d backup table(s); not dropping because repair stopped with an error", len(backups))
			}
			return res, fmt.Errorf("%s %w", prefix, err)
		}
		res.Repaired++
		if backupPath != "" {
			backups = append(backups, backupPath)
		}
		logger.Printf("%s OK %s (backup %s)", prefix, path, backupPath)
		if _, werr := fmt.Fprintln(out, path); werr != nil {
			return res, werr
		}
	}

	if opt.DropBackup && len(backups) > 0 {
		logger.Printf("Dropping %d backup table(s) at end of successful run…", len(backups))
		for _, backupPath := range backups {
			if opt.DryRun {
				logger.Printf("DRY-RUN drop backup %s", backupPath)
				res.BackupsDropped++
				continue
			}
			logger.Printf("Dropping backup %s", backupPath)
			if err := c.DropTable(ctx, backupPath); err != nil {
				return res, fmt.Errorf("drop backup %s: %w", backupPath, err)
			}
			res.BackupsDropped++
		}
	}

	return res, nil
}

// repairOne repairs one table. On success it returns the backup path created
// for later optional drop; on dry-run it returns the planned backup path.
func repairOne(ctx context.Context, c *client.Client, path string, opt Options, logger *log.Logger) (string, error) {
	if err := assertNeedsRepair(ctx, c, path); err != nil {
		return "", err
	}

	parent, name, err := client.SplitPath(path)
	if err != nil {
		return "", err
	}
	tempName := opt.TempPrefix + name
	backupName := name + opt.BackupSuffix
	tempPath := client.JoinPath(parent, tempName)
	backupPath := client.JoinPath(parent, backupName)

	for _, extra := range []string{tempPath, backupPath} {
		exists, err := c.PathExists(ctx, extra)
		if err != nil {
			return "", err
		}
		if exists {
			return "", fmt.Errorf("%s: helper path already exists: %s", path, extra)
		}
	}

	if opt.DryRun {
		msg := fmt.Sprintf("DRY-RUN %s: copy→%s, move %s→%s, move %s→%s",
			path, tempPath, path, backupPath, tempPath, path)
		if opt.DropBackup {
			msg += "; backup will be dropped at end"
		}
		logger.Printf("%s", msg)
		return backupPath, nil
	}

	logger.Printf("%s: copying to %s with pool_kind=%q", path, tempPath, opt.PoolKind)
	if err := c.CopyWithStorage(ctx, path, parent, tempName, opt.PoolKind); err != nil {
		return "", fmt.Errorf("%s: copy: %w", path, err)
	}
	if err := assertRepaired(ctx, c, tempPath); err != nil {
		return "", fmt.Errorf("%s: temp copy check: %w", path, err)
	}

	logger.Printf("%s: renaming %s → %s", path, path, backupPath)
	if err := c.MoveTable(ctx, path, backupPath); err != nil {
		return "", fmt.Errorf("%s: rename to backup: %w", path, err)
	}

	logger.Printf("%s: renaming %s → %s", path, tempPath, path)
	if err := c.MoveTable(ctx, tempPath, path); err != nil {
		return "", fmt.Errorf("%s: rename temp to original: %w", path, err)
	}
	if err := assertRepaired(ctx, c, path); err != nil {
		return "", fmt.Errorf("%s: post-check: %w", path, err)
	}

	if !opt.DropBackup {
		logger.Printf("%s: backup kept at %s", path, backupPath)
	}
	return backupPath, nil
}

func assertNeedsRepair(ctx context.Context, c *client.Client, path string) error {
	resp, err := c.MustDescribeOK(ctx, path, true, false)
	if err != nil {
		return err
	}
	table := resp.GetPathDescription().GetTable()
	if table == nil {
		return fmt.Errorf("%s: SchemeDescribe has no PathDescription.Table", path)
	}
	cl := legacy.ClassifyPartitionConfig(table.GetPartitionConfig())
	switch cl.Status {
	case legacy.AlreadyRepaired:
		return fmt.Errorf("%w: %s (%s)", ErrAlreadyRepaired, path, cl.Reason)
	case legacy.NeedsRepair:
		return nil
	default:
		return fmt.Errorf("%s: unsafe: %s (repair procedure not applicable)", path, cl.Reason)
	}
}

func assertRepaired(ctx context.Context, c *client.Client, path string) error {
	resp, err := c.MustDescribeOK(ctx, path, true, false)
	if err != nil {
		return err
	}
	table := resp.GetPathDescription().GetTable()
	if table == nil {
		return fmt.Errorf("%s: describe has no Table", path)
	}
	cl := legacy.ClassifyPartitionConfig(table.GetPartitionConfig())
	if cl.Status != legacy.AlreadyRepaired {
		return fmt.Errorf("%s: expected repaired, got %s (%s)", path, cl.Status, cl.Reason)
	}
	return nil
}
