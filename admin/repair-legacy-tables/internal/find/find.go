package find

import (
	"context"
	"fmt"
	"io"
	"log"
	"sort"
	"strings"

	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/client"
	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/internal/legacy"
	schemeop "github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/schemeop"
)

// Options for the find walk.
type Options struct {
	StartPath  string
	IncludeSys bool
	Out        io.Writer // legacy tables: "path\\treason"
	Log        *log.Logger
}

// Result summarizes a find run.
type Result struct {
	TablesChecked int
	Legacy        int
	Errors        int
}

// Run walks the scheme tree via SchemeDescribe and prints legacy tables.
func Run(ctx context.Context, c *client.Client, opt Options) (*Result, error) {
	if opt.Out == nil {
		return nil, fmt.Errorf("Out writer is required")
	}
	logger := opt.Log
	if logger == nil {
		logger = log.New(io.Discard, "", 0)
	}
	start := strings.TrimRight(opt.StartPath, "/")
	if start == "" {
		return nil, fmt.Errorf("empty start path")
	}

	res := &Result{}
	queue := []string{start}
	seen := map[string]struct{}{}

	for len(queue) > 0 {
		path := queue[0]
		queue = queue[1:]
		if _, ok := seen[path]; ok {
			continue
		}
		seen[path] = struct{}{}

		resp, err := c.MustDescribeOK(ctx, path, true, true)
		if err != nil {
			res.Errors++
			logger.Printf("ERROR describing %s: %v", path, err)
			continue
		}
		pd := resp.GetPathDescription()
		if pd == nil {
			res.Errors++
			logger.Printf("ERROR %s: empty PathDescription", path)
			continue
		}

		selfType := schemeop.EPathType_EPathTypeDir
		if pd.Self != nil {
			selfType = pd.Self.GetPathType()
		}

		if legacy.IsTablePathType(selfType) {
			res.TablesChecked++
			cl := legacy.ClassifyPartitionConfig(pd.GetTable().GetPartitionConfig())
			switch cl.Status {
			case legacy.NeedsRepair:
				res.Legacy++
				line := path + "\t" + cl.Reason + "\n"
				if _, err := io.WriteString(opt.Out, line); err != nil {
					return res, err
				}
				logger.Printf("LEGACY %s: %s", path, cl.Reason)
			case legacy.Unsafe:
				logger.Printf("UNSAFE %s: %s (not listed for repair)", path, cl.Reason)
			}
			continue
		}

		if !legacy.IsDirectoryPathType(selfType) && path != start {
			// Unknown / non-walkable node.
			continue
		}

		children := pd.GetChildren()
		logger.Printf("Listed %s: %d child(ren)", path, len(children))

		var next []string
		for _, ch := range children {
			name := ch.GetName()
			if name == "" {
				continue
			}
			if !opt.IncludeSys && strings.HasPrefix(name, ".") {
				continue
			}
			childPath := client.JoinPath(path, name)
			pt := ch.GetPathType()
			switch {
			case legacy.IsDirectoryPathType(pt):
				next = append(next, childPath)
			case legacy.IsTablePathType(pt):
				// Describe table separately to get PartitionConfig.
				queue = append(queue, childPath)
			default:
				// skip indexes, topics, etc.
			}
		}
		sort.Strings(next)
		queue = append(queue, next...)
	}

	return res, nil
}
