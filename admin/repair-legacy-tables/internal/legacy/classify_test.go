package legacy

import (
	"testing"

	"google.golang.org/protobuf/proto"

	schemeop "github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/schemeop"
)

func TestClassifyNeedsRepairEmpty(t *testing.T) {
	cl := ClassifyPartitionConfig(&schemeop.TPartitionConfig{})
	if cl.Status != NeedsRepair {
		t.Fatalf("got %v (%s)", cl.Status, cl.Reason)
	}
}

func TestClassifyAlreadyRepaired(t *testing.T) {
	pc := &schemeop.TPartitionConfig{
		ColumnFamilies: []*schemeop.TFamilyDescription{
			{
				Id: proto.Uint32(0),
				Name: proto.String("default"),
				StorageConfig: &schemeop.TStorageConfig{
					Data: &schemeop.TStorageSettings{PreferredPoolKind: proto.String("ssd")},
				},
			},
		},
	}
	cl := ClassifyPartitionConfig(pc)
	if cl.Status != AlreadyRepaired {
		t.Fatalf("got %v (%s)", cl.Status, cl.Reason)
	}
}

func TestClassifyUnsafeChannelProfile(t *testing.T) {
	pc := &schemeop.TPartitionConfig{
		ChannelProfileId: proto.Uint32(0),
	}
	cl := ClassifyPartitionConfig(pc)
	if cl.Status != Unsafe {
		t.Fatalf("got %v (%s)", cl.Status, cl.Reason)
	}
}

func TestClassifyUnsafeFamilyWithoutStorage(t *testing.T) {
	pc := &schemeop.TPartitionConfig{
		ColumnFamilies: []*schemeop.TFamilyDescription{
			{Id: proto.Uint32(0), Name: proto.String("default")},
		},
	}
	cl := ClassifyPartitionConfig(pc)
	if cl.Status != Unsafe {
		t.Fatalf("got %v (%s)", cl.Status, cl.Reason)
	}
}
