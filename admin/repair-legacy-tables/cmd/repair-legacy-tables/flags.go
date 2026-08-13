package main

import (
	"flag"
	"fmt"
	"strings"
)

// stringFlagsNeedingValue are long option names that must be followed by a value.
// Used to catch mistakes like `--endpoint --pool-kind …` before stdlib flag
// consumes the next flag name as the value and then stops parsing.
var stringFlagsNeedingValue = []string{
	"endpoint",
	"token-file",
	"ca-file",
	"timeout",
	"database",
	"path",
	"output",
	"tables-file",
	"pool-kind",
	"temp-prefix",
	"backup-suffix",
}

func isFlagName(arg string) bool {
	if arg == "-" || arg == "--" {
		return false
	}
	return strings.HasPrefix(arg, "-")
}

func flagBaseName(arg string) string {
	arg = strings.TrimLeft(arg, "-")
	if i := strings.IndexByte(arg, '='); i >= 0 {
		arg = arg[:i]
	}
	return arg
}

// validateFlagArgs reports missing values for string flags (e.g. bare --endpoint).
func validateFlagArgs(args []string) error {
	need := make(map[string]struct{}, len(stringFlagsNeedingValue))
	for _, n := range stringFlagsNeedingValue {
		need[n] = struct{}{}
	}

	for i := 0; i < len(args); i++ {
		arg := args[i]
		if arg == "--" {
			return nil
		}
		if !strings.HasPrefix(arg, "-") {
			continue
		}
		// --name=value form already has a value
		if strings.Contains(arg, "=") {
			name := flagBaseName(arg)
			if _, ok := need[name]; ok {
				val := arg[strings.IndexByte(arg, '=')+1:]
				if val == "" {
					return fmt.Errorf("--%s requires a value (e.g. --%s <value>)", name, name)
				}
			}
			continue
		}
		name := flagBaseName(arg)
		if _, ok := need[name]; !ok {
			continue
		}
		if i+1 >= len(args) || isFlagName(args[i+1]) {
			switch name {
			case "endpoint":
				return fmt.Errorf("--endpoint requires a value, e.g. grpc://host:2135")
			case "tables-file":
				return fmt.Errorf("--tables-file requires a path to the list from find --output")
			case "pool-kind":
				return fmt.Errorf("--pool-kind requires a value, e.g. ssd")
			case "database":
				return fmt.Errorf("--database requires a path, e.g. /Root/database")
			default:
				return fmt.Errorf("--%s requires a value", name)
			}
		}
		i++ // skip the value
	}
	return nil
}

func parseFlags(fs *flag.FlagSet, args []string) error {
	if err := validateFlagArgs(args); err != nil {
		return err
	}
	if err := fs.Parse(args); err != nil {
		return err
	}
	rest := fs.Args()
	if len(rest) == 0 {
		return nil
	}
	for _, a := range rest {
		if isFlagName(a) {
			return fmt.Errorf("unexpected argument %q after non-flag token %q; check that every option has its value", a, rest[0])
		}
	}
	return fmt.Errorf("unexpected argument %q", rest[0])
}
