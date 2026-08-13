package legacy

import (
	"fmt"

	schemeop "github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/schemeop"
)

// Status of a table relative to the column-family repair procedure.
type Status int

const (
	// NeedsRepair: no ColumnFamilies / empty families — safe to repair.
	NeedsRepair Status = iota
	// AlreadyRepaired: family 0 has StorageConfig — skip and continue.
	AlreadyRepaired
	// Unsafe: procedure must not be applied (stop on repair).
	Unsafe
)

func (s Status) String() string {
	switch s {
	case NeedsRepair:
		return "needs_repair"
	case AlreadyRepaired:
		return "already_repaired"
	case Unsafe:
		return "unsafe"
	default:
		return fmt.Sprintf("status(%d)", int(s))
	}
}

// Classification is the result of inspecting PartitionConfig.
type Classification struct {
	Status Status
	Reason string
}

// ClassifyPartitionConfig decides whether a table needs / can be repaired.
//
// Aligns with find_legacy_tables.py (legacy = missing family 0 StorageConfig)
// and the PDF safety rules (do not apply when ChannelProfileId is set or when
// ColumnFamilies exist but are incomplete).
func ClassifyPartitionConfig(pc *schemeop.TPartitionConfig) Classification {
	if pc == nil {
		return Classification{Status: NeedsRepair, Reason: "no PartitionConfig"}
	}
	if pc.ChannelProfileId != nil {
		return Classification{
			Status: Unsafe,
			Reason: "PartitionConfig.ChannelProfileId is set",
		}
	}

	families := pc.GetColumnFamilies()
	if len(families) == 0 {
		return Classification{
			Status: NeedsRepair,
			Reason: "no ColumnFamilies entry with Id: 0",
		}
	}

	var family0 *schemeop.TFamilyDescription
	for _, f := range families {
		if f.GetId() == 0 {
			family0 = f
			break
		}
	}
	if family0 == nil {
		return Classification{
			Status: Unsafe,
			Reason: "ColumnFamilies present but no entry with Id: 0",
		}
	}
	if hasUsableStorageConfig(family0.GetStorageConfig()) {
		return Classification{
			Status: AlreadyRepaired,
			Reason: "family 0 has StorageConfig",
		}
	}
	return Classification{
		Status: Unsafe,
		Reason: "family 0 has no StorageConfig",
	}
}

func hasUsableStorageConfig(sc *schemeop.TStorageConfig) bool {
	if sc == nil {
		return false
	}
	return sc.SysLog != nil || sc.Log != nil || sc.Data != nil
}

// IsDirectoryPathType reports whether the path type should be walked.
func IsDirectoryPathType(t schemeop.EPathType) bool {
	switch t {
	case schemeop.EPathType_EPathTypeDir, schemeop.EPathType_EPathTypeSubDomain:
		return true
	default:
		return false
	}
}

// IsTablePathType reports whether the path is a row-table eligible for repair.
func IsTablePathType(t schemeop.EPathType) bool {
	return t == schemeop.EPathType_EPathTypeTable
}
