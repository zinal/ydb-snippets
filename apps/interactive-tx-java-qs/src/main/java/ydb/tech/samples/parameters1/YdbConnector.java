package ydb.tech.samples.parameters1;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Properties;
import tech.ydb.auth.iam.CloudAuthHelper;
import tech.ydb.core.auth.StaticCredentials;
import tech.ydb.core.grpc.GrpcTransport;
import tech.ydb.core.grpc.GrpcTransportBuilder;
import tech.ydb.query.QueryClient;
import tech.ydb.scheme.SchemeClient;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.table.TableClient;

/**
 * The helper class which creates the YDB connection from the set of properties.
 *
 * @author mzinal
 */
public class YdbConnector implements AutoCloseable {

    private static final org.slf4j.Logger LOG = org.slf4j.LoggerFactory.getLogger(YdbConnector.class);

    private final GrpcTransport transport;
    private final SchemeClient schemeClient;
    private final TableClient tableClient;
    private final QueryClient queryClient;
    private final SessionRetryContext retryCtx;
    private final String database;
    private final Config config;

    public YdbConnector(Config config) {
        GrpcTransportBuilder builder = GrpcTransport
                .forConnectionString(config.getConnectionString());
        switch (config.getAuthMode()) {
            case ENV:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getAuthProviderFromEnviron());
                break;
            case STATIC:
                builder = builder.withAuthProvider(
                        new StaticCredentials(config.getStaticLogin(), config.getStaticPassword()));
                break;
            case METADATA:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getMetadataAuthProvider());
                break;
            case SAKEY:
                builder = builder.withAuthProvider(
                        CloudAuthHelper.getServiceAccountFileAuthProvider(config.getSaKeyFile()));
                break;
            case NONE:
                break;
        }
        String tlsCertFile = config.getTlsCertificateFile();
        if (tlsCertFile != null && tlsCertFile.length() > 0) {
            byte[] cert;
            try {
                cert = Files.readAllBytes(Paths.get(tlsCertFile));
            } catch (IOException ix) {
                throw new RuntimeException("Failed to read file " + tlsCertFile, ix);
            }
            builder.withSecureConnection(cert);
        }

        GrpcTransport tempTransport = builder.build();
        this.database = tempTransport.getDatabase();
        try {
            this.schemeClient = SchemeClient.newClient(tempTransport).build();
            this.tableClient = QueryClient.newTableClient(tempTransport)
                    .sessionPoolSize(0, config.getPoolSize())
                    .build();
            this.queryClient = QueryClient.newClient(tempTransport)
                    .sessionPoolMinSize(1)
                    .sessionPoolMaxSize(config.getPoolSize())
                    .build();
            this.retryCtx = SessionRetryContext.create(this.queryClient)
                    .idempotent(true)
                    .build();
            this.transport = tempTransport;
            tempTransport = null; // to avoid closing below
        } finally {
            if (tempTransport != null) {
                tempTransport.close();
            }
        }
        this.config = config;
    }

    public YdbConnector(Properties props) {
        this(new Config(props));
    }

    public YdbConnector(Properties props, String prefix) {
        this(new Config(props, prefix));
    }

    public Config getConfig() {
        return config;
    }

    public SchemeClient getSchemeClient() {
        return schemeClient;
    }

    public TableClient getTableClient() {
        return tableClient;
    }

    public QueryClient getQueryClient() {
        return queryClient;
    }

    public SessionRetryContext getRetryCtx() {
        return retryCtx;
    }

    public String getDatabase() {
        return database;
    }

    @Override
    public void close() {
        if (schemeClient != null) {
            try {
                schemeClient.close();
            } catch (Exception ex) {
                LOG.warn("SchemeClient closing threw an exception", ex);
            }
        }
        if (queryClient != null) {
            try {
                queryClient.close();
            } catch (Exception ex) {
                LOG.warn("QueryClient closing threw an exception", ex);
            }
        }
        if (transport != null) {
            try {
                transport.close();
            } catch (Exception ex) {
                LOG.warn("GrpcTransport closing threw an exception", ex);
            }
        }
    }

    public static final class Config {

        private String connectionString;
        private AuthMode authMode = AuthMode.NONE;
        private String saKeyFile;
        private String staticLogin;
        private String staticPassword;
        private String tlsCertificateFile;
        private int poolSize = 2 * (1 + Runtime.getRuntime().availableProcessors());
        private final String prefix;
        private final Properties properties = new Properties();

        public Config() {
            this.prefix = "ydb.";
        }

        public Config(Properties props) {
            this(props, null);
        }

        public Config(Properties props, String prefix) {
            if (prefix == null) {
                prefix = "ydb.";
            }
            this.prefix = prefix;
            this.connectionString = props.getProperty(prefix + "url");
            this.authMode = AuthMode.valueOf(props.getProperty(prefix + "auth.mode", "NONE"));
            this.saKeyFile = props.getProperty(prefix + "auth.sakey");
            this.staticLogin = props.getProperty(prefix + "auth.username");
            this.staticPassword = props.getProperty(prefix + "auth.password");
            this.tlsCertificateFile = props.getProperty(prefix + "cafile");
            String spool = props.getProperty(prefix + "poolSize");
            if (spool != null && spool.length() > 0) {
                poolSize = Integer.parseInt(spool);
            }
            this.properties.putAll(props);
        }

        public static Config fromFile(String fname) {
            return fromFile(fname, null);
        }

        public static Config fromFile(String fname, String prefix) {
            byte[] data;
            try {
                data = Files.readAllBytes(Paths.get(fname));
            } catch (IOException ix) {
                throw new RuntimeException("Failed to read file " + fname, ix);
            }
            Properties props = new Properties();
            try {
                props.loadFromXML(new ByteArrayInputStream(data));
            } catch (IOException ix) {
                throw new RuntimeException("Failed to parse properties file " + fname, ix);
            }
            return new Config(props, prefix);
        }

        public String getPrefix() {
            return prefix;
        }

        public String getConnectionString() {
            return connectionString;
        }

        public void setConnectionString(String connectionString) {
            this.connectionString = connectionString;
        }

        public AuthMode getAuthMode() {
            return authMode;
        }

        public void setAuthMode(AuthMode authMode) {
            if (authMode == null) {
                authMode = AuthMode.NONE;
            }
            this.authMode = authMode;
        }

        public String getSaKeyFile() {
            return saKeyFile;
        }

        public void setSaKeyFile(String saKeyFile) {
            this.saKeyFile = saKeyFile;
        }

        public String getStaticLogin() {
            return staticLogin;
        }

        public void setStaticLogin(String staticLogin) {
            this.staticLogin = staticLogin;
        }

        public String getStaticPassword() {
            return staticPassword;
        }

        public void setStaticPassword(String staticPassword) {
            this.staticPassword = staticPassword;
        }

        public String getTlsCertificateFile() {
            return tlsCertificateFile;
        }

        public void setTlsCertificateFile(String tlsCertificateFile) {
            this.tlsCertificateFile = tlsCertificateFile;
        }

        public int getPoolSize() {
            return poolSize;
        }

        public void setPoolSize(int poolSize) {
            if (poolSize <= 0) {
                poolSize = 2 * (1 + Runtime.getRuntime().availableProcessors());
            }
            this.poolSize = poolSize;
        }

        public Properties getProperties() {
            return properties;
        }

    }

    public static enum AuthMode {

        NONE,
        ENV,
        STATIC,
        METADATA,
        SAKEY

    }
}