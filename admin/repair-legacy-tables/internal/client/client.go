package client

import (
	"context"
	"crypto/tls"
	"fmt"
	"net"
	"net/url"
	"os"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/proto"

	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/msgbus"
	schemeop "github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/schemeop"
	"github.com/zinal/ydb-snippets/admin/repair-legacy-tables/pkg/kikimr/txproxy"
)

// MessageBus status codes (ydb/core/client/base/msgbus.h).
const (
	MStatusOK         = 1
	MStatusInProgress = 129
)

// StatusPathDoesNotExist from NKikimrScheme::EStatus.
const StatusPathDoesNotExist = 2

const defaultPollTimeout = 120 * time.Second

// Client talks to the legacy private TGRpcServer.
type Client struct {
	conn   *grpc.ClientConn
	stub   msgbus.TGRpcServerClient
	token  string
	timeout time.Duration
}

// Options for connecting to YDB.
type Options struct {
	Endpoint string
	Token    string
	CAFile   string
	Insecure bool // for grpcs: skip certificate verification
	Timeout  time.Duration
}

// ResolveToken returns token from --token-file or YDB_TOKEN (anonymous if neither).
func ResolveToken(tokenFile string) (string, error) {
	if tokenFile != "" {
		data, err := os.ReadFile(tokenFile)
		if err != nil {
			return "", fmt.Errorf("read token file: %w", err)
		}
		token := strings.TrimSpace(string(data))
		if token == "" {
			return "", fmt.Errorf("token file %q is empty", tokenFile)
		}
		for _, prefix := range []string{"OAuth ", "Bearer ", "Login "} {
			if strings.HasPrefix(token, prefix) {
				token = strings.TrimSpace(strings.TrimPrefix(token, prefix))
				break
			}
		}
		return token, nil
	}
	if v, ok := os.LookupEnv("YDB_TOKEN"); ok {
		v = strings.TrimSpace(v)
		if v != "" {
			return v, nil
		}
	}
	return "", nil
}

// Dial opens a gRPC connection to the legacy TGRpcServer.
func Dial(ctx context.Context, opt Options) (*Client, error) {
	scheme, host, port, err := parseEndpoint(opt.Endpoint)
	if err != nil {
		return nil, err
	}
	target := net.JoinHostPort(host, fmt.Sprintf("%d", port))

	var creds credentials.TransportCredentials
	switch scheme {
	case "grpc":
		creds = insecure.NewCredentials()
	case "grpcs":
		if opt.Insecure {
			creds = credentials.NewTLS(&tls.Config{
				MinVersion:         tls.VersionTLS12,
				InsecureSkipVerify: true, //nolint:gosec // intentional for lab/dev
			})
		} else if opt.CAFile != "" {
			creds, err = credentials.NewClientTLSFromFile(opt.CAFile, "")
			if err != nil {
				return nil, fmt.Errorf("load CA file: %w", err)
			}
		} else {
			creds = credentials.NewTLS(&tls.Config{MinVersion: tls.VersionTLS12})
		}
	default:
		return nil, fmt.Errorf("unsupported endpoint scheme %q", scheme)
	}

	timeout := opt.Timeout
	if timeout <= 0 {
		timeout = defaultPollTimeout
	}

	conn, err := grpc.DialContext(ctx, target,
		grpc.WithTransportCredentials(creds),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(64<<20),
			grpc.MaxCallSendMsgSize(64<<20),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("dial %s: %w", target, err)
	}

	return &Client{
		conn:    conn,
		stub:    msgbus.NewTGRpcServerClient(conn),
		token:   opt.Token,
		timeout: timeout,
	}, nil
}

func parseEndpoint(endpoint string) (scheme, host string, port int, err error) {
	raw := strings.TrimSpace(endpoint)
	if raw == "" {
		return "", "", 0, fmt.Errorf("empty endpoint")
	}
	if !strings.Contains(raw, "://") {
		raw = "grpc://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", "", 0, fmt.Errorf("parse endpoint: %w", err)
	}
	scheme = strings.ToLower(u.Scheme)
	if scheme != "grpc" && scheme != "grpcs" {
		return "", "", 0, fmt.Errorf("unsupported endpoint scheme %q (use grpc:// or grpcs://)", scheme)
	}
	host = u.Hostname()
	if host == "" {
		return "", "", 0, fmt.Errorf("endpoint has no host: %q", endpoint)
	}
	if u.Port() == "" {
		return scheme, host, 2135, nil
	}
	var p int
	if _, err = fmt.Sscanf(u.Port(), "%d", &p); err != nil || p <= 0 {
		return "", "", 0, fmt.Errorf("invalid port in endpoint: %q", endpoint)
	}
	return scheme, host, p, nil
}

// Close closes the underlying connection.
func (c *Client) Close() error {
	if c.conn == nil {
		return nil
	}
	return c.conn.Close()
}

func (c *Client) applyToken(set func(string)) {
	if c.token != "" {
		set(c.token)
	}
}

// Describe returns SchemeDescribe response for path.
func (c *Client) Describe(ctx context.Context, path string, partitionConfig, children bool) (*msgbus.TResponse, error) {
	req := &msgbus.TSchemeDescribe{
		Path: proto.String(path),
		Options: &schemeop.TDescribeOptions{
			ReturnPartitioningInfo: proto.Bool(false),
			ReturnPartitionConfig:  proto.Bool(partitionConfig),
			ReturnChildren:         proto.Bool(children),
		},
	}
	c.applyToken(func(t string) { req.SecurityToken = proto.String(t) })

	ctx, cancel := context.WithTimeout(ctx, c.timeout)
	defer cancel()

	resp, err := c.stub.SchemeDescribe(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("SchemeDescribe %s: %w", path, err)
	}
	return resp, nil
}

// PathExists reports whether path is present in the scheme tree.
func (c *Client) PathExists(ctx context.Context, path string) (bool, error) {
	resp, err := c.Describe(ctx, path, false, false)
	if err != nil {
		return false, err
	}
	if resp.GetStatus() == MStatusOK {
		return true, nil
	}
	if resp.GetSchemeStatus() == StatusPathDoesNotExist {
		return false, nil
	}
	reason := strings.ToLower(resp.GetErrorReason())
	if strings.Contains(reason, "does not exist") ||
		strings.Contains(reason, "path not found") ||
		strings.Contains(reason, "doesn't exist") {
		return false, nil
	}
	return false, fmt.Errorf("SchemeDescribe %s: status=%d schemeStatus=%d reason=%q",
		path, resp.GetStatus(), resp.GetSchemeStatus(), resp.GetErrorReason())
}

// MustDescribeOK is Describe that requires MSTATUS_OK.
func (c *Client) MustDescribeOK(ctx context.Context, path string, partitionConfig, children bool) (*msgbus.TResponse, error) {
	resp, err := c.Describe(ctx, path, partitionConfig, children)
	if err != nil {
		return nil, err
	}
	if resp.GetStatus() != MStatusOK {
		return nil, fmt.Errorf("SchemeDescribe %s: status=%d reason=%q",
			path, resp.GetStatus(), resp.GetErrorReason())
	}
	return resp, nil
}

// SchemeOperation executes one ModifyScheme and waits until completion.
func (c *Client) SchemeOperation(ctx context.Context, ms *schemeop.TModifyScheme) (*msgbus.TResponse, error) {
	pollMs := uint32(c.timeout / time.Millisecond)
	if pollMs == 0 {
		pollMs = uint32(defaultPollTimeout / time.Millisecond)
	}
	req := &msgbus.TSchemeOperation{
		Transaction: &txproxy.TTransaction{
			ModifyScheme: ms,
		},
		PollOptions: &msgbus.TFlatTxPollOptions{
			Timeout: proto.Uint32(pollMs),
		},
	}
	c.applyToken(func(t string) { req.SecurityToken = proto.String(t) })

	callCtx, cancel := context.WithTimeout(ctx, c.timeout+30*time.Second)
	defer cancel()

	resp, err := c.stub.SchemeOperation(callCtx, req)
	if err != nil {
		return nil, fmt.Errorf("SchemeOperation: %w", err)
	}
	if resp.GetStatus() == MStatusInProgress {
		if resp.FlatTxId == nil {
			return nil, fmt.Errorf("SchemeOperation INPROGRESS without FlatTxId")
		}
		resp, err = c.pollStatus(callCtx, resp.FlatTxId, pollMs)
		if err != nil {
			return nil, err
		}
	}
	if resp.GetStatus() != MStatusOK {
		return nil, fmt.Errorf("SchemeOperation failed: status=%d reason=%q",
			resp.GetStatus(), resp.GetErrorReason())
	}
	return resp, nil
}

func (c *Client) pollStatus(ctx context.Context, tx *msgbus.TFlatTxId, pollMs uint32) (*msgbus.TResponse, error) {
	req := &msgbus.TSchemeOperationStatus{
		FlatTxId: tx,
		PollOptions: &msgbus.TFlatTxPollOptions{
			Timeout: proto.Uint32(pollMs),
		},
	}
	c.applyToken(func(t string) { req.SecurityToken = proto.String(t) })
	resp, err := c.stub.SchemeOperationStatus(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("SchemeOperationStatus: %w", err)
	}
	return resp, nil
}

// CopyWithStorage copies sourcePath into destParent/destName with default family StorageConfig.
func (c *Client) CopyWithStorage(ctx context.Context, sourcePath, destParent, destName, poolKind string) error {
	ms := &schemeop.TModifyScheme{
		WorkingDir:    proto.String(destParent),
		OperationType: schemeop.EOperationType_ESchemeOpCreateTable.Enum(),
		CreateTable: &schemeop.TTableDescription{
			Name:          proto.String(destName),
			CopyFromTable: proto.String(sourcePath),
			PartitionConfig: &schemeop.TPartitionConfig{
				ColumnFamilies: []*schemeop.TFamilyDescription{
					{
						Id:   proto.Uint32(0),
						Name: proto.String("default"),
						StorageConfig: &schemeop.TStorageConfig{
							SysLog: &schemeop.TStorageSettings{PreferredPoolKind: proto.String(poolKind)},
							Log:    &schemeop.TStorageSettings{PreferredPoolKind: proto.String(poolKind)},
							Data:   &schemeop.TStorageSettings{PreferredPoolKind: proto.String(poolKind)},
						},
					},
				},
			},
		},
	}
	_, err := c.SchemeOperation(ctx, ms)
	return err
}

// MoveTable renames/moves a table (full paths).
func (c *Client) MoveTable(ctx context.Context, src, dst string) error {
	ms := &schemeop.TModifyScheme{
		OperationType: schemeop.EOperationType_ESchemeOpMoveTable.Enum(),
		MoveTable: &schemeop.TMove{
			SrcPath: proto.String(src),
			DstPath: proto.String(dst),
		},
	}
	_, err := c.SchemeOperation(ctx, ms)
	return err
}

// DropTable drops a table by full path.
func (c *Client) DropTable(ctx context.Context, path string) error {
	parent, name, err := SplitPath(path)
	if err != nil {
		return err
	}
	ms := &schemeop.TModifyScheme{
		WorkingDir:    proto.String(parent),
		OperationType: schemeop.EOperationType_ESchemeOpDropTable.Enum(),
		Drop:          &schemeop.TDrop{Name: proto.String(name)},
	}
	_, err = c.SchemeOperation(ctx, ms)
	return err
}

// SplitPath splits "/a/b/c" into ("/a/b", "c").
func SplitPath(path string) (parent, name string, err error) {
	path = strings.TrimRight(path, "/")
	if path == "" || path == "/" {
		return "", "", fmt.Errorf("invalid table path %q", path)
	}
	i := strings.LastIndex(path, "/")
	if i <= 0 {
		return "", "", fmt.Errorf("invalid table path %q", path)
	}
	return path[:i], path[i+1:], nil
}

// JoinPath joins parent and name.
func JoinPath(parent, name string) string {
	return strings.TrimRight(parent, "/") + "/" + name
}
