APP     := repair-legacy-tables
MODULE  := github.com/zinal/ydb-snippets/admin/repair-legacy-tables
BIN_DIR := bin

# Pure-Go static binary: avoids host GLIBC version requirements on target hosts.
export CGO_ENABLED ?= 0

GO_BUILD_FLAGS ?= -trimpath -ldflags='-s -w'

.PHONY: all build test generate tidy clean

all: build

generate:
	./generate.sh

tidy:
	go mod tidy

build:
	mkdir -p $(BIN_DIR)
	CGO_ENABLED=$(CGO_ENABLED) go build $(GO_BUILD_FLAGS) -o $(BIN_DIR)/$(APP) ./cmd/repair-legacy-tables

test:
	CGO_ENABLED=$(CGO_ENABLED) go test ./...

clean:
	rm -rf $(BIN_DIR)
