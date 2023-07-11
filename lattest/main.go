package main

import (
	"context"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"golang.org/x/exp/rand"

	"github.com/ydb-platform/ydb-go-sdk/v3"
	"github.com/ydb-platform/ydb-go-sdk/v3/balancers"
	"github.com/ydb-platform/ydb-go-sdk/v3/table"
	"github.com/ydb-platform/ydb-go-sdk/v3/table/options"
	"github.com/ydb-platform/ydb-go-sdk/v3/table/result"
	"github.com/ydb-platform/ydb-go-sdk/v3/table/types"
	yc "github.com/ydb-platform/ydb-go-yc"
)

type YdbAuthMode int

const (
	YdbAuthNone YdbAuthMode = iota
	YdbAuthStatic
	YdbAuthMeta
	YdbAuthSaKey
)

var ydbAuthModeMap = map[string]YdbAuthMode{
	"":       YdbAuthNone,
	"none":   YdbAuthNone,
	"static": YdbAuthStatic,
	"meta":   YdbAuthMeta,
	"sakey":  YdbAuthSaKey,
}

func ydbAuth(mode YdbAuthMode, q url.Values, u *url.URL) ydb.Option {
	switch mode {
	case YdbAuthStatic:
		p, _ := u.User.Password()
		return ydb.WithStaticCredentials(u.User.Username(), p)
	case YdbAuthMeta:
		return yc.WithMetadataCredentials()
	case YdbAuthSaKey:
		return yc.WithServiceAccountKeyFileCredentials(q.Get("saKeyFile"))
	default:
		return ydb.WithAnonymousCredentials()
	}
}

func ydbConnect(addr string) (*ydb.Driver, error) {
	u, err := url.Parse(addr)
	if err != nil {
		return nil, err
	}
	q := u.Query()
	database := u.Path
	if len(database) == 0 {
		database = q.Get("database")
	}
	if !strings.HasPrefix(database, "/") {
		database = "/" + database
	}
	tls := false
	if strings.ToLower(u.Scheme) == "grpcs" {
		tls = true
	}
	if q.Has("tls") {
		tls, _ = strconv.ParseBool(q.Get("tls"))
	}
	serverless := false
	if q.Has("serverless") {
		serverless, _ = strconv.ParseBool(q.Get("serverless"))
	}
	var ydbUrl string
	if tls {
		ydbUrl = "grpcs://" + u.Host + database
	} else {
		ydbUrl = "grpc://" + u.Host + database
	}
	authModeStr := strings.ToLower(q.Get("authMode"))
	authMode, authModeFound := ydbAuthModeMap[authModeStr]
	if !authModeFound {
		return nil, fmt.Errorf("unknown auth mode: %q", authModeStr)
	}
	certFile := q.Get("tlsCertFile")
	if len(certFile) == 0 {
		certFile = "/dev/null"
	}

	bconf := balancers.Default()
	if serverless {
		bconf = balancers.SingleConn()
	}

	var con *ydb.Driver
	func() {
		poolSize := 10
		ydbContext, ctxCloseFn := context.WithTimeout(context.Background(), 10*time.Second)
		defer ctxCloseFn()

		con, err = ydb.Open(ydbContext, ydbUrl,
			ydb.WithUserAgent("lattest"),
			ydb.WithSessionPoolSizeLimit(poolSize),
			ydb.WithBalancer(bconf),
			ydb.WithSessionPoolIdleThreshold(time.Hour),
			ydb.WithCertificatesFromFile(certFile),
			ydbAuth(authMode, q, u))
	}()
	if err != nil {
		return nil, err
	}
	return con, nil
}

func runTransaction(con *ydb.Driver, iter int) (total int, err error) {
	ydbContext, ctxCloseFn := context.WithCancel(context.Background())
	defer ctxCloseFn()
	total = 0
	err = con.Table().Do(
		ydbContext, func(ctx context.Context, sess table.Session) error {
			var txc *table.TransactionControl
			var trans table.Transaction
			var data result.Result
			for i := 0; i < iter; i++ {
				input := int32(rand.Intn(10000))
				txcWork := txc
				if txcWork == nil {
					txcWork = table.SerializableReadWriteTxControl()
				}
				trans, data, err = sess.Execute(ctx, txcWork,
					"DECLARE $p AS Int32; SELECT 1+$p AS out;",
					table.NewQueryParameters(
						table.ValueParam("$p", types.Int32Value(input)),
					), options.WithKeepInCache(true),
				)
				if err != nil {
					return err
				}
				if txc == nil {
					txc = table.SerializableReadWriteTxControl(table.WithTx(trans))
				}
				if data.NextResultSet(ctx) {
					if data.NextRow() {
						var value int32
						if err = data.Scan(&value); err != nil {
							return err
						}
						if value != input+1 {
							return fmt.Errorf("illegal query output, got %q, expected %q", value, input+1)
						}
					}
				}
				total = total + int(input)
			}
			return nil
		}, table.WithIdempotent())
	return total, err
}

func main() {
	addr := "grpc://localhost:2136/local"
	if len(os.Args) > 1 {
		addr = os.Args[1]
	}
	operTotal := 100
	if len(os.Args) > 2 {
		var err error
		operTotal, err = strconv.Atoi(os.Args[2])
		if err != nil {
			panic(err)
		}
	}

	fmt.Println("Starting up...")
	ydbContext, ctxCloseFn := context.WithCancel(context.Background())
	defer ctxCloseFn()
	connectStart := time.Now()
	con, err := ydbConnect(addr)
	connectFinish := time.Now()
	if err != nil {
		panic(err)
	}
	defer con.Close(ydbContext)
	fmt.Println("Connected! Duraction = " + connectFinish.Sub(connectStart).String())

	rand.Seed(uint64(time.Now().UnixNano()))

	operStart := time.Now()

	operDone := 0
	operIter := 0
	for operTotal > operDone {
		operStep := 3 + rand.Intn(8)
		if operDone+operStep > operTotal {
			operStep = operTotal - operDone
		}
		_, err = runTransaction(con, operStep)
		if err != nil {
			panic(err)
		}
		operDone += operStep
		operIter += 1
	}

	operFinish := time.Now()

	avgTime := float64(operFinish.Sub(operStart).Milliseconds()) / float64(operTotal)

	fmt.Printf("Processed! Ops = %d, iterations = %d, duraction = %s, avg = %f msec\n",
		operTotal, operIter, operFinish.Sub(operStart).String(), avgTime)

	fmt.Println("Shutting down...")
}
