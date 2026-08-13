APP     := repair-legacy-tables
MODULE  := github.com/zinal/ydb-snippets/admin/repair-legacy-tables
BIN_DIR := bin

.PHONY: all build test generate tidy clean

all: build

generate:
	./generate.sh

tidy:
	go mod tidy

build:
	mkdir -p $(BIN_DIR)
	go build -o $(BIN_DIR)/$(APP) ./cmd/repair-legacy-tables

test:
	go test ./...

clean:
	rm -rf $(BIN_DIR)
