package main

import (
	"context"
	"fmt"
	"os"
	"path"
	"time"

	ydbenv "github.com/ydb-platform/ydb-go-sdk-auth-environ"
	"github.com/ydb-platform/ydb-go-sdk/v3"
	"github.com/ydb-platform/ydb-go-sdk/v3/table"
	"github.com/ydb-platform/ydb-go-sdk/v3/table/types"
)

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	dsn, exists := os.LookupEnv("YDB_CONNECTION_STRING")
	if !exists {
		panic("YDB_CONNECTION_STRING environment variable not defined")
	}

	db, err := ydb.Open(ctx,
		dsn,
		ydbenv.WithEnvironCredentials(ctx),
	)
	if err != nil {
		panic(fmt.Errorf("connect error: %w", err))
	}
	defer func() { _ = db.Close(ctx) }()

	fmt.Println("Connection established")

	tableName := path.Join(db.Name(), "evil/table1")

	db.Table().Do(ctx, func(ctx context.Context, session table.Session) (err error) {
		return session.DropTable(ctx, tableName)
	}, table.WithIdempotent())

	err = createTable(ctx, db, tableName)
	if err != nil {
		panic(fmt.Errorf("table creation error: %w", err))
	}

	fmt.Printf("Table `%s` created\n", tableName)

	err = normalBulkUpsert(ctx, db, tableName)
	if err != nil {
		panic(fmt.Errorf("normal bulk upsert error: %w", err))
	}

	fmt.Println("'Normal' BulkUpsert succeeded.")

	err = evilBulkUpsert(ctx, db, tableName)
	if err != nil {
		panic(fmt.Errorf("evil bulk upsert error: %w", err))
	}

	fmt.Println("'Evil' BulkUpsert succeeded.")
}

func createTable(ctx context.Context, db *ydb.Driver, tableName string) (err error) {
	sqlTable1 := fmt.Sprintf("CREATE TABLE `%s` (a Int32 NOT NULL, b Utf8, c JsonDocument, d Int32, PRIMARY KEY(a))", tableName)
	return db.Table().Do(ctx, func(ctx context.Context, session table.Session) (err error) {
		return session.ExecuteSchemeQuery(ctx, sqlTable1)
	}, table.WithIdempotent())
}

func normalBulkUpsert(ctx context.Context, db *ydb.Driver, tableName string) error {
	rows := make([]types.Value, 0, 2)

	columns := make([]types.StructValueOption, 0, 2)
	v := types.Int32Value(101)
	columns = append(columns, types.StructFieldValue("a", v))
	v = types.TextValue("row-101")
	columns = append(columns, types.StructFieldValue("b", v))
	v = types.JSONDocumentValue("{\"a\": 101}")
	columns = append(columns, types.StructFieldValue("c", v))
	v = types.Int32Value(111)
	columns = append(columns, types.StructFieldValue("d", v))
	rows = append(rows, types.StructValue(columns...))

	columns = make([]types.StructValueOption, 0, 2)
	v = types.Int32Value(102)
	columns = append(columns, types.StructFieldValue("a", v))
	v = types.TextValue("row-102")
	columns = append(columns, types.StructFieldValue("b", v))
	v = types.JSONDocumentValue("{\"a\": 102}")
	columns = append(columns, types.StructFieldValue("c", v))
	v = types.Int32Value(112)
	columns = append(columns, types.StructFieldValue("d", v))
	rows = append(rows, types.StructValue(columns...))

	return db.Table().Do(ctx, func(ctx context.Context, sess table.Session) error {
		return sess.BulkUpsert(ctx, tableName, types.ListValue(rows...))
	})
}

func evilBulkUpsert(ctx context.Context, db *ydb.Driver, tableName string) (err error) {
	rows := make([]types.Value, 0, 2)

	columns := make([]types.StructValueOption, 0, 2)
	v := types.Int32Value(201)
	columns = append(columns, types.StructFieldValue("a", v))
	v = types.TextValue("row-201")
	columns = append(columns, types.StructFieldValue("b", v))
	v = types.JSONDocumentValue("{\"a\": 201}")
	columns = append(columns, types.StructFieldValue("c", v))
	rows = append(rows, types.StructValue(columns...))

	columns = make([]types.StructValueOption, 0, 2)
	v = types.Int32Value(202)
	columns = append(columns, types.StructFieldValue("a", v))
	v = types.TextValue("row-202")
	columns = append(columns, types.StructFieldValue("b", v))
	v = types.Int32Value(212)
	columns = append(columns, types.StructFieldValue("d", v))
	rows = append(rows, types.StructValue(columns...))

	return db.Table().Do(ctx, func(ctx context.Context, sess table.Session) error {
		return sess.BulkUpsert(ctx, tableName, types.ListValue(rows...))
	})
}
