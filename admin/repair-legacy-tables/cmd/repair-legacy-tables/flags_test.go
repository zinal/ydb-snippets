package main

import (
	"strings"
	"testing"
)

func TestValidateFlagArgsMissingEndpointValue(t *testing.T) {
	err := validateFlagArgs([]string{
		"--endpoint", "--pool-kind", "ssd", "--tables-file", "legacy_tables.txt",
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "--endpoint requires a value") {
		t.Fatalf("got %v", err)
	}
}

func TestValidateFlagArgsOK(t *testing.T) {
	err := validateFlagArgs([]string{
		"--endpoint", "grpc://host:2135",
		"--pool-kind", "ssd",
		"--tables-file", "legacy_tables.txt",
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestValidateFlagArgsEqualsForm(t *testing.T) {
	err := validateFlagArgs([]string{
		"--endpoint=grpc://host:2135",
		"--tables-file=legacy_tables.txt",
		"--pool-kind=ssd",
	})
	if err != nil {
		t.Fatal(err)
	}
}
