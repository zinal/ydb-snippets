package repair

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadTablePaths(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "tables.txt")
	content := `# comment
/Root/db/t1	no ColumnFamilies entry with Id: 0
/Root/db/t2

/Root/db/t1
/Root/db/t3
`
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	got, err := LoadTablePaths(path)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"/Root/db/t1", "/Root/db/t2", "/Root/db/t3"}
	if len(got) != len(want) {
		t.Fatalf("got %v want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("got %v want %v", got, want)
		}
	}
}
